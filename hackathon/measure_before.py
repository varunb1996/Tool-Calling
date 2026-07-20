"""
Hackathon Step 0/BEFORE - run one representative diagnosis query through
the naive tools and measure the real damage with tiktoken.

Representative scenario: Aarav asks the diagnoser to pull together
everything relevant to one project from his email, calendar, and the web,
to scope a build brief. This is exactly the kind of multi-tool query the
diagnoser is meant to handle well.

Run: python -m hackathon.measure_before
Writes hackathon/before_results.json
"""

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from diagnoser.system_prompt import DIAGNOSER_SYSTEM_PROMPT
from diagnoser.tools_naive import search_web_naive, search_gmail_naive, search_calendar_naive
from hackathon.token_count import count_tokens

USER_QUERY = (
    "Search my email and calendar for anything related to the Q3 reporting "
    "automation project over the last year, and check the web for current "
    "no-code tools I could use - I need to scope my build brief."
)

# Deterministic stand-ins for what the model would extract as each tool's
# argument, so BEFORE and AFTER call the tools with identical inputs and
# only the implementation differs - an apples-to-apples comparison.
GMAIL_QUERY = "Q3 reporting automation"
CALENDAR_QUERY = "Q3 reporting automation"
WEB_QUERY = "best no-code workflow automation tools 2026"


def main():
    print("Running naive search_gmail...")
    gmail_result = search_gmail_naive(GMAIL_QUERY)
    gmail_tokens = count_tokens(gmail_result)
    print(f"  {gmail_result['email_count']} emails returned, {gmail_tokens:,} tokens")

    print("Running naive search_calendar...")
    calendar_result = search_calendar_naive(CALENDAR_QUERY)
    calendar_tokens = count_tokens(calendar_result)
    print(f"  {calendar_result['event_count']} events returned, {calendar_tokens:,} tokens")

    print("Running naive search_web (max_results=100)...")
    web_result = search_web_naive(WEB_QUERY)
    web_tokens = count_tokens(web_result)
    print(f"  {len(web_result['results'])} results returned, {web_tokens:,} tokens")

    system_tokens = count_tokens(DIAGNOSER_SYSTEM_PROMPT)
    user_tokens = count_tokens(USER_QUERY)

    total_payload_tokens = (
        system_tokens + user_tokens + gmail_tokens + calendar_tokens + web_tokens
    )

    results = {
        "query": USER_QUERY,
        "tool_queries": {"gmail": GMAIL_QUERY, "calendar": CALENDAR_QUERY, "web": WEB_QUERY},
        "tokens": {
            "system_prompt": system_tokens,
            "user_query": user_tokens,
            "search_gmail_naive": gmail_tokens,
            "search_calendar_naive": calendar_tokens,
            "search_web_naive": web_tokens,
            "total_tool_output": gmail_tokens + calendar_tokens + web_tokens,
            "total_payload": total_payload_tokens,
        },
        "counts": {
            "emails_returned": gmail_result["email_count"],
            "events_returned": calendar_result["event_count"],
            "web_results_returned": len(web_result["results"]),
        },
    }

    print(f"\nTotal tool-output tokens: {results['tokens']['total_tool_output']:,}")
    print(f"Total payload tokens (system + user + tools): {total_payload_tokens:,}")

    out_path = Path(__file__).parent / "before_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
