"""
Step 2 - The index is the NCERT move: a small, machine-readable inventory
that routes a query to the right chunk(s) without ever loading all the
data. Build time (here) is separate from query time (retrieve.py) - the
index gets built once; every query just reads this file.

Run: python -m diagnoser.rag.build_index
Writes diagnoser/rag/index.json
"""

import json
from pathlib import Path

from hackathon.token_count import count_tokens

CHUNKS_DIR = Path(__file__).parent / "chunks"
INDEX_PATH = Path(__file__).parent / "index.json"


def build_chunk_metadata(chunk_path: Path, source: str):
    records = json.loads(chunk_path.read_text(encoding="utf-8"))
    dates = [r["date"] for r in records]
    labels = sorted({label for r in records for label in r.get("labels", [])})

    if source == "gmail":
        participants = sorted({r["from"] for r in records})
    else:
        participants = sorted({a for r in records for a in r.get("attendees", [])})

    return {
        "chunk_id": chunk_path.stem,
        "source": source,
        "year": chunk_path.stem.split("_")[-1],
        "date_range": {"start": min(dates), "end": max(dates)},
        "record_count": len(records),
        "labels": labels,
        "participants": participants,
        "token_count": count_tokens(records),
        "path": str(chunk_path.relative_to(Path(__file__).parent)),
    }


def main():
    index = []
    for chunk_path in sorted(CHUNKS_DIR.glob("*.json")):
        source = "gmail" if chunk_path.stem.startswith("gmail") else "calendar"
        entry = build_chunk_metadata(chunk_path, source)
        index.append(entry)
        print(f"  {entry['chunk_id']}: {entry['record_count']} records, "
              f"labels={entry['labels']}, {entry['token_count']:,} tokens")

    INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")
    total_chunks = len(index)
    total_index_tokens = count_tokens(index)
    print(f"\n{total_chunks} chunks indexed. index.json itself is {total_index_tokens:,} tokens "
          f"- this is what retrieval reads FIRST, instead of loading every chunk.")
    print(f"Written to {INDEX_PATH}")


if __name__ == "__main__":
    main()
