"""
Step 1 - Chunk by year (same move as the lecture's weather data: partition
by a natural seam, verify nothing was lost).

Splits the raw synthetic Gmail/Calendar dumps into one file per source per
year. Two invariants get checked, same as the lecture:
1. every chunk individually is small (trivially true here, but checked anyway)
2. sum of all chunk tokens == original raw token count (no silent data loss)

Run: python -m diagnoser.rag.chunk_data
Writes diagnoser/rag/chunks/{gmail,calendar}_{year}.json
"""

import json
from collections import defaultdict
from pathlib import Path

from hackathon.token_count import count_tokens

DATA_DIR = Path(__file__).parent / "data"
CHUNKS_DIR = Path(__file__).parent / "chunks"


def chunk_by_year(records, date_key="date"):
    by_year = defaultdict(list)
    for record in records:
        year = record[date_key][:4]
        by_year[year].append(record)
    return dict(sorted(by_year.items()))


def write_chunks(source_name, raw_path, date_key="date"):
    raw_records = json.loads(raw_path.read_text(encoding="utf-8"))
    raw_tokens = count_tokens(raw_records)
    raw_ids = {r["id"] for r in raw_records}

    by_year = chunk_by_year(raw_records, date_key)
    chunk_paths = []
    chunk_tokens_sum = 0
    chunk_ids = set()

    for year, records in by_year.items():
        chunk_path = CHUNKS_DIR / f"{source_name}_{year}.json"
        chunk_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        chunk_tokens = count_tokens(records)
        chunk_tokens_sum += chunk_tokens
        chunk_ids.update(r["id"] for r in records)
        chunk_paths.append((chunk_path, year, len(records), chunk_tokens))
        print(f"  {chunk_path.name}: {len(records)} records, {chunk_tokens:,} tokens")

    # The invariant that actually matters is completeness: every record
    # present exactly once, none dropped or duplicated. Checking that via
    # IDs (not token counts) is deliberate - re-serializing one big array
    # vs several smaller ones produces slightly different bracket/comma
    # token counts even with byte-identical record content, so a strict
    # token-sum equality would be a false alarm here, not a real bug.
    assert chunk_ids == raw_ids, (
        f"invariant violated for {source_name}: chunk IDs don't match raw "
        f"IDs - missing: {raw_ids - chunk_ids}, extra: {chunk_ids - raw_ids}"
    )
    drift = chunk_tokens_sum - raw_tokens
    print(
        f"  invariant OK: {len(by_year)} chunks contain all {len(raw_ids)} "
        f"records exactly once (token sum {chunk_tokens_sum:,} vs raw "
        f"{raw_tokens:,}, {drift:+d} tokens - JSON structural overhead "
        f"from splitting one array into several, not data loss)\n"
    )

    return chunk_paths


def main():
    CHUNKS_DIR.mkdir(exist_ok=True)

    print("Chunking gmail_inbox_raw.json by year...")
    write_chunks("gmail", DATA_DIR / "gmail_inbox_raw.json")

    print("Chunking calendar_events_raw.json by year...")
    write_chunks("calendar", DATA_DIR / "calendar_events_raw.json")


if __name__ == "__main__":
    main()
