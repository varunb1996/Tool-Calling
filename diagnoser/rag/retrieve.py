"""
Steps 3-4 - retrieval (index-filtered, keyword only, no embeddings) and
pre-aggregation (collapse to the resolution the query actually needs),
wired back in as the RAG-optimized versions of search_gmail, search_calendar,
and search_web.

Query flow for gmail/calendar (pre-chunked local data):
  1. read index.json (831 tokens) - NOT the chunks themselves
  2. keep only chunks whose labels overlap the query's keywords
  3. load only those chunk files
  4. within them, keep only records whose subject/labels also match
  5. pre-aggregate: return {date, who, subject, snippet}, not full bodies

Query flow for web (live API, nothing pre-chunked to index):
  1. call Tavily with max_results=100, same as the naive baseline
  2. score each result's title+content against the query's keywords
  3. keep only the top-K most relevant, and truncate content to a snippet

Same idea both times: never hand the model more than it needs to answer
THIS query, and never load more than you had to touch to find that out.
"""

import json
import os
import re
from pathlib import Path

from tavily import TavilyClient

RAG_DIR = Path(__file__).parent
INDEX_PATH = RAG_DIR / "index.json"

STOPWORDS = {"the", "a", "an", "of", "for", "to", "and", "in", "on", "with", "is", "are"}

_tavily_client = None


def _get_tavily():
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _tavily_client


def _keywords(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def _label_keywords(label: str) -> set:
    return _keywords(label.replace("-", " ").replace(":", " "))


def _load_index():
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _overlap_threshold(query_kw: set) -> int:
    """Single-keyword overlap over-matches: a query like 'reporting
    automation' will match any AI newsletter that happens to say
    'automation' once. Discovered this the same way the lecture found its
    missing 'month' key - by actually running a query and noticing the
    match count was too high (33 emails when only 28 are real). Requiring
    at least 2 overlapping keywords (when the query has 2+) fixes it
    without needing embeddings."""
    return 2 if len(query_kw) >= 2 else 1


def _matching_chunks(query: str, source: str):
    """Index-level filter: which chunks are even worth opening?"""
    query_kw = _keywords(query)
    threshold = _overlap_threshold(query_kw)
    index = _load_index()
    matches = []
    for entry in index:
        if entry["source"] != source:
            continue
        chunk_label_kw = set()
        for label in entry["labels"]:
            chunk_label_kw |= _label_keywords(label)
        if len(query_kw & chunk_label_kw) >= threshold:
            matches.append(entry)
    return matches


def _record_matches(record, query_kw, source):
    record_kw = set()
    for label in record.get("labels", []):
        record_kw |= _label_keywords(label)
    subject = record.get("subject") or record.get("title") or ""
    record_kw |= _keywords(subject)
    threshold = _overlap_threshold(query_kw)
    return len(query_kw & record_kw) >= threshold


def search_gmail_rag(query: str) -> dict:
    query_kw = _keywords(query)
    matched_chunks = _matching_chunks(query, "gmail")
    matched_records = []
    for chunk_meta in matched_chunks:
        records = json.loads((RAG_DIR / chunk_meta["path"]).read_text(encoding="utf-8"))
        matched_records.extend(r for r in records if _record_matches(r, query_kw, "gmail"))

    matched_records.sort(key=lambda r: r["date"])
    aggregated = [
        {
            "date": r["date"],
            "from": r["from_name"],
            "subject": r["subject"],
            "snippet": r["body"][:160] + ("..." if len(r["body"]) > 160 else ""),
        }
        for r in matched_records
    ]
    return {
        "query": query,
        "chunks_opened": [c["chunk_id"] for c in matched_chunks],
        "email_count": len(aggregated),
        "emails": aggregated,
    }


def search_calendar_rag(query: str) -> dict:
    query_kw = _keywords(query)
    matched_chunks = _matching_chunks(query, "calendar")
    matched_records = []
    for chunk_meta in matched_chunks:
        records = json.loads((RAG_DIR / chunk_meta["path"]).read_text(encoding="utf-8"))
        matched_records.extend(r for r in records if _record_matches(r, query_kw, "calendar"))

    matched_records.sort(key=lambda r: r["date"])
    aggregated = [
        {
            "date": r["date"],
            "title": r["title"],
            "attendees": r["attendees"],
            "snippet": r["description"][:160] + ("..." if len(r["description"]) > 160 else ""),
        }
        for r in matched_records
    ]
    return {
        "query": query,
        "chunks_opened": [c["chunk_id"] for c in matched_chunks],
        "event_count": len(aggregated),
        "events": aggregated,
    }


def search_web_rag(query: str, top_k: int = 5) -> dict:
    client = _get_tavily()
    result = client.search(query=query, max_results=100, include_answer=True)
    query_kw = _keywords(query)

    def score(r):
        return len(query_kw & _keywords(r["title"] + " " + r["content"]))

    ranked = sorted(result.get("results", []), key=score, reverse=True)[:top_k]
    return {
        "answer": result.get("answer"),
        "results": [
            {
                "title": r["title"],
                "url": r["url"],
                "snippet": r["content"][:300] + ("..." if len(r["content"]) > 300 else ""),
            }
            for r in ranked
        ],
    }


RAG_TOOL_FUNCTIONS = {
    "search_web": search_web_rag,
    "search_gmail": search_gmail_rag,
    "search_calendar": search_calendar_rag,
}
