"""
Hackathon Step 0 - "break it on purpose": the deliberately naive, wasteful
versions of the diagnoser's tools. These exist ONLY to produce the BEFORE
measurement; diagnoser/tools.py (the Rep 2/3 versions) is left untouched so
that submission stays reproducible.

Three surfaces, three ways to be wasteful:
- search_web_naive: Tavily max_results bumped 5 -> 100, full content per result
- search_gmail_naive: ignores the query, returns the ENTIRE synthetic inbox
- search_calendar_naive: ignores the query, returns the ENTIRE synthetic calendar

Real-world naive tools rarely look this extreme, but the pattern is
realistic: a Gmail/Calendar wrapper that fetches "everything in range" and
lets the model sort it out is a completely ordinary first implementation,
the same way the lecture's naive weather tool fetched 10 years of hourly
data for a two-day question.
"""

import json
import os
from pathlib import Path

from tavily import TavilyClient

DATA_DIR = Path(__file__).parent / "rag" / "data"

_tavily_client = None


def _get_tavily():
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _tavily_client


def search_web_naive(query: str) -> dict:
    """Same as diagnoser.tools.search_web but max_results raised 5 -> 100
    per the hackathon instructions, with full (untruncated) content per
    result - this alone is enough to surface the token problem."""
    client = _get_tavily()
    result = client.search(query=query, max_results=100, include_answer=True)
    return {
        "answer": result.get("answer"),
        "results": [
            {"title": r["title"], "url": r["url"], "content": r["content"]}
            for r in result.get("results", [])
        ],
    }


def search_gmail_naive(query: str) -> dict:
    """Deliberately does not filter by `query` at all - returns the whole
    inbox, exactly as a naive 'fetch everything, let the model figure it
    out' wrapper would."""
    emails = json.loads((DATA_DIR / "gmail_inbox_raw.json").read_text(encoding="utf-8"))
    return {"query": query, "email_count": len(emails), "emails": emails}


def search_calendar_naive(query: str) -> dict:
    """Same anti-pattern as search_gmail_naive: ignores the query, returns
    every event ever created."""
    events = json.loads((DATA_DIR / "calendar_events_raw.json").read_text(encoding="utf-8"))
    return {"query": query, "event_count": len(events), "events": events}


# JSON specs - same shape the model would see whether the implementation
# behind them is naive or RAG-optimized. This matters: Step 4/5 of the
# hackathon wires a BETTER implementation behind the SAME tool contract,
# so the model-facing interface never changes, only what happens inside.

NAIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the live web for current information relevant to the user's workflow diagnosis.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_gmail",
            "description": "Search the user's email for messages relevant to their workflow.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look for, e.g. project name or topic"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_calendar",
            "description": "Search the user's calendar for meetings/events relevant to their workflow.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look for, e.g. project name or topic"}},
                "required": ["query"],
            },
        },
    },
]

NAIVE_TOOL_FUNCTIONS = {
    "search_web": search_web_naive,
    "search_gmail": search_gmail_naive,
    "search_calendar": search_calendar_naive,
}
