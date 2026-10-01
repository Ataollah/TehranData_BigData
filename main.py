import argparse
import json
import re
import sqlite3
from pathlib import Path


WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def extract_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from extract_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from extract_strings(child)


def read_document_text(path):
    content = path.read_text(encoding="utf-8")
    try:
        document = json.loads(content)
    except json.JSONDecodeError:
        return content
    return " ".join(extract_strings(document))


def build_inverted_index(corpus_dir, database_path):
    corpus_dir = Path(corpus_dir)
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    documents = sorted(corpus_dir.rglob("*.txt"))

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS word_files ("
            "word TEXT NOT NULL, filename TEXT NOT NULL, "
            "PRIMARY KEY (word, filename))"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_word_files_filename "
            "ON word_files (filename)"
        )
        connection.execute("DELETE FROM word_files")

        for path in documents:
            words = {
                word.casefold()
                for word in WORD_PATTERN.findall(read_document_text(path))
            }
            filename = path.relative_to(corpus_dir).as_posix()
            connection.executemany(
                "INSERT INTO word_files (word, filename) VALUES (?, ?)",
                ((word, filename) for word in words),
            )

        pair_count = connection.execute(
            "SELECT COUNT(*) FROM word_files"
        ).fetchone()[0]

    return len(documents), pair_count


def find_word_files(database_path, word):
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT filename FROM word_files WHERE word = ? ORDER BY filename",
            (word.casefold(),),
        ).fetchall()
    return [row[0] for row in rows]


def main():
    parser = argparse.ArgumentParser(
        description="Build a SQLite inverted index for Hamshahri text files."
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("data/Hamshahri_data"),
        help="Directory containing the .txt documents.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/hamshahri_inverted_index.db"),
        help="SQLite database path (rebuilt each run).",
    )
    parser.add_argument(
        "word",
        nargs="?",
        help="Find documents containing this word instead of rebuilding the index.",
    )
    args = parser.parse_args()

    if args.word is not None:
        if not args.database.exists():
            parser.error(
                f"{args.database} does not exist; run without a word to build the index first."
            )
        filenames = find_word_files(args.database, args.word)
        if filenames:
            print("\n".join(filenames))
        else:
            print(f"No documents found for: {args.word}")
        return

    document_count, pair_count = build_inverted_index(
        args.corpus_dir, args.database
    )
    print(
        f"Indexed {document_count} documents into {args.database} "
        f"({pair_count} word-document pairs)."
    )


if __name__ == "__main__":
    main()
