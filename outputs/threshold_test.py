"""
Rep 3 - find the point where tool_choice="auto" routing starts breaking.

Method: a fixed battery of test queries, each with one "correct" tool.
We run the battery repeatedly against a GROWING tool set (2 -> 6 tools),
using a single completions call per query (no multi-turn conversation -
we only care about the model's FIRST routing decision). At each stage we
only ask the queries relevant to tools introduced so far, and record
whether the model picked the right tool, the wrong tool, no tool at all,
or hallucinated a tool name that isn't in the tool set.

Two of the Rep 3 tools (lookup_tool_info, estimate_pricing_tier) were
deliberately written to semantically overlap with search_web and
estimate_time_saved, to try to induce confusion rather than wait for it.

Run: python -m outputs.threshold_test
Writes outputs/threshold_results.json (raw data) - failure_log.md is
written by hand afterwards from these results.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq, BadRequestError

from diagnoser.tools import BASE_TOOLS, EXTRA_TOOLS

load_dotenv()

MODEL = "llama-3.3-70b-versatile"
client = Groq(api_key=os.environ["GROQ_API_KEY"])

ALL_TOOLS_BY_NAME = {t["function"]["name"]: t for t in BASE_TOOLS + EXTRA_TOOLS}

# stage: (tool names included, [(query, expected_tool), ...] newly introduced)
STAGES = [
    (
        ["search_web", "estimate_time_saved"],
        [
            ("What's the current pricing for the Claude API right now?", "search_web"),
            ("What's the newest AI agent framework people are using in 2026?", "search_web"),
            ("What's the going rate for a Tavily subscription right now?", "search_web"),
            ("I spend 5 hours a week on manual reporting, over a 6 week pilot, at $40/hour - what's the savings?", "estimate_time_saved"),
            ("I spend 3 hours a week manually triaging support tickets, over a 4-week pilot, at $25/hour - what's the savings?", "estimate_time_saved"),
            ("How many hours would I save automating a 2 hour/week task for 12 weeks at $50/hour?", "estimate_time_saved"),
        ],
    ),
    (
        ["search_web", "estimate_time_saved", "score_workflow"],
        [
            ("Score this workflow: lead follow-up with frequency=4, pain=5, access=5, ai_fit=5, speed=4.", "score_workflow"),
            ("Score this workflow: invoice processing with frequency=2, pain=5, access=2, ai_fit=3, speed=2.", "score_workflow"),
        ],
    ),
    (
        ["search_web", "estimate_time_saved", "score_workflow", "save_diagnosis_note"],
        [
            ("Please save a note for the hypothesis phase saying I need to add a measurable result clause.", "save_diagnosis_note"),
            ("Record a note in the observation phase: user described stalling after picking a category, not a workflow.", "save_diagnosis_note"),
        ],
    ),
    (
        ["search_web", "estimate_time_saved", "score_workflow", "save_diagnosis_note", "lookup_tool_info"],
        [
            ("What does Zapier actually do?", "lookup_tool_info"),
            ("Tell me about n8n.", "lookup_tool_info"),
        ],
    ),
    (
        ["search_web", "estimate_time_saved", "score_workflow", "save_diagnosis_note", "lookup_tool_info", "estimate_pricing_tier"],
        [
            ("If I expect 500 monthly active users, what pricing tier would that be?", "estimate_pricing_tier"),
            ("We might get 50 monthly users at first - what tier is that?", "estimate_pricing_tier"),
        ],
    ),
]


def run_query(query, tools):
    """Returns the name of the first tool picked, None if no tool was
    called, or the sentinel "<malformed_call>" if the model's generation
    itself was rejected by the API as invalid tool-call syntax (a
    generation failure, distinct from picking the wrong tool)."""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": query}],
                tools=tools,
                tool_choice="auto",
            )
            break
        except BadRequestError:
            if attempt == 2:
                return "<malformed_call>"
    message = response.choices[0].message
    if not message.tool_calls:
        return None
    # only look at the first tool call for routing purposes
    return message.tool_calls[0].function.name


def main():
    results = []
    cumulative_queries = []  # (query, expected_tool) accumulated across stages
    out_path = Path(__file__).parent / "threshold_results.json"

    try:
        for stage_tools, new_queries in STAGES:
            cumulative_queries.extend(new_queries)
            tools = [ALL_TOOLS_BY_NAME[name] for name in stage_tools]
            stage_result = {"tool_count": len(stage_tools), "tools": stage_tools, "cases": []}

            for query, expected in cumulative_queries:
                picked = run_query(query, tools)
                correct = picked == expected
                stage_result["cases"].append(
                    {
                        "query": query,
                        "expected": expected,
                        "picked": picked,
                        "correct": correct,
                    }
                )
                marker = "OK" if correct else "MISROUTE"
                print(f"[{len(stage_tools)} tools] {marker:9s} expected={expected!r:25s} picked={picked!r:25s} query={query[:60]!r}")

            n = len(stage_result["cases"])
            errors = sum(1 for c in stage_result["cases"] if not c["correct"])
            stage_result["error_rate"] = errors / n
            print(f"--- stage with {len(stage_tools)} tools: {errors}/{n} misroutes ---\n")
            results.append(stage_result)
    finally:
        # Always persist whatever we collected, even if a stage crashed
        # partway (e.g. hitting a provider's rate limit) - partial real
        # data beats losing the whole run.
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Results (possibly partial) written to {out_path}")


if __name__ == "__main__":
    main()
