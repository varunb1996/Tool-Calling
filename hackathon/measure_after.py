"""
Hackathon AFTER - same representative query, same tool inputs as
measure_before.py, but through the RAG-optimized implementations
(diagnoser/rag/retrieve.py) instead of the naive ones.

Run: python -m hackathon.measure_after
Writes hackathon/after_results.json
"""

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from diagnoser.system_prompt import DIAGNOSER_SYSTEM_PROMPT
from diagnoser.rag.retrieve import search_web_rag, search_gmail_rag, search_calendar_rag
from hackathon.token_count import count_tokens
from hackathon.measure_before import USER_QUERY, GMAIL_QUERY, CALENDAR_QUERY, WEB_QUERY


def main():
    print("Running RAG search_gmail...")
    gmail_result = search_gmail_rag(GMAIL_QUERY)
    gmail_tokens = count_tokens(gmail_result)
    print(f"  opened chunks {gmail_result['chunks_opened']}, "
          f"{gmail_result['email_count']} emails returned, {gmail_tokens:,} tokens")

    print("Running RAG search_calendar...")
    calendar_result = search_calendar_rag(CALENDAR_QUERY)
    calendar_tokens = count_tokens(calendar_result)
    print(f"  opened chunks {calendar_result['chunks_opened']}, "
          f"{calendar_result['event_count']} events returned, {calendar_tokens:,} tokens")

    print("Running RAG search_web (max_results=100 internally, top 5 kept)...")
    web_result = search_web_rag(WEB_QUERY)
    web_tokens = count_tokens(web_result)
    print(f"  {len(web_result['results'])} results returned, {web_tokens:,} tokens")

    system_tokens = count_tokens(DIAGNOSER_SYSTEM_PROMPT)
    user_tokens = count_tokens(USER_QUERY)
    index_tokens = count_tokens(json.loads((Path(__file__).parent.parent / "diagnoser/rag/index.json").read_text()))

    total_payload_tokens = (
        system_tokens + user_tokens + gmail_tokens + calendar_tokens + web_tokens
    )

    results = {
        "query": USER_QUERY,
        "tool_queries": {"gmail": GMAIL_QUERY, "calendar": CALENDAR_QUERY, "web": WEB_QUERY},
        "tokens": {
            "system_prompt": system_tokens,
            "user_query": user_tokens,
            "search_gmail_rag": gmail_tokens,
            "search_calendar_rag": calendar_tokens,
            "search_web_rag": web_tokens,
            "total_tool_output": gmail_tokens + calendar_tokens + web_tokens,
            "total_payload": total_payload_tokens,
            "index_json_itself": index_tokens,
        },
        "counts": {
            "emails_returned": gmail_result["email_count"],
            "events_returned": calendar_result["event_count"],
            "web_results_returned": len(web_result["results"]),
            "gmail_chunks_opened": gmail_result["chunks_opened"],
            "calendar_chunks_opened": calendar_result["chunks_opened"],
        },
    }

    print(f"\nTotal tool-output tokens: {results['tokens']['total_tool_output']:,}")
    print(f"Total payload tokens (system + user + tools): {total_payload_tokens:,}")

    out_path = Path(__file__).parent / "after_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
