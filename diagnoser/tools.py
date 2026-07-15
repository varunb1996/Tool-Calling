"""
Tool functions + their JSON specs for the diagnoser.

Two things live side by side for every tool, on purpose:
1. A plain Python function that does the real work (the "deterministic layer").
2. A JSON schema dict describing that function to the model (the "contract").

The model only ever sees #2. It never sees #1's source code. This is why
the description in #2 has to fully explain *when* to use the tool and what
its arguments mean - the model is deciding purely from that text.
"""

import os
from tavily import TavilyClient

_tavily_client = None


def _get_tavily():
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _tavily_client


def search_web(query: str) -> dict:
    """Real-time web search via Tavily. This is what fixes hallucination
    about anything after the model's training cutoff."""
    client = _get_tavily()
    result = client.search(query=query, max_results=5, include_answer=True)
    return {
        "answer": result.get("answer"),
        "results": [
            {"title": r["title"], "url": r["url"], "content": r["content"]}
            for r in result.get("results", [])
        ],
    }


def estimate_time_saved(hours_per_week: float, weeks: int, hourly_rate: float) -> dict:
    """Pure calculator - no external call. Ties back to the MVP plan's
    before/after time-saved metric."""
    total_hours = hours_per_week * weeks
    total_value = total_hours * hourly_rate
    return {
        "total_hours_saved": total_hours,
        "total_value_saved": total_value,
        "currency_note": "same currency unit as hourly_rate",
    }


# --- JSON specs (Groq/OpenAI "function calling" format) -------------------
# Each one includes a worked example pair in the description, per the
# Exercise 2 feedback the practice set calls back to.

BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the live web for current, real-time information: "
                "recent tool releases, current pricing, current best "
                "practices, or anything that may have changed after this "
                "model's training cutoff. Do NOT use this for pure math or "
                "for information already given in the conversation.\n"
                "Example: query='pricing for Claude Opus 4.5 API' -> "
                "returns an answer string plus up to 5 titled web results "
                "with URLs and snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A focused search query, written like a search "
                            "engine query, not a full sentence. "
                            "Example: 'Tavily API free tier limits'."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_time_saved",
            "description": (
                "Calculate hours and money saved over a period once a "
                "manual, repeated task is automated. Use this whenever the "
                "user gives a per-week time cost and asks about savings, "
                "ROI, or payback for automating a workflow. Do NOT use this "
                "for anything that requires looking up current information.\n"
                "Example: hours_per_week=5, weeks=6, hourly_rate=40 -> "
                "{'total_hours_saved': 30, 'total_value_saved': 1200}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_per_week": {
                        "type": "number",
                        "description": "Hours currently spent on the manual task each week, e.g. 5.5",
                    },
                    "weeks": {
                        "type": "integer",
                        "description": "Number of weeks the automation runs for, e.g. 6",
                    },
                    "hourly_rate": {
                        "type": "number",
                        "description": "The person's fully-loaded hourly cost in local currency, e.g. 40",
                    },
                },
                "required": ["hours_per_week", "weeks", "hourly_rate"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "search_web": search_web,
    "estimate_time_saved": estimate_time_saved,
}


# --- Rep 3: deliberately expanding the tool set ----------------------------
# score_workflow is a clean addition (distinct purpose, no overlap).
# lookup_tool_info and estimate_pricing_tier are deliberately designed to
# semantically overlap with search_web and estimate_time_saved, respectively,
# so that threshold_test.py has a real chance of observing tool_choice="auto"
# pick the wrong one.

def score_workflow(frequency: int, pain: int, access: int, ai_fit: int, speed: int) -> dict:
    """Rank a candidate workflow using the MVP plan's 5-factor rubric.
    Each factor is scored 1-5."""
    total = frequency + pain + access + ai_fit + speed
    if total >= 20:
        recommendation = "strong candidate - prioritize"
    elif total >= 12:
        recommendation = "moderate candidate - needs sharper scoping"
    else:
        recommendation = "weak candidate - look for a different workflow"
    return {"total_score": total, "max_score": 25, "recommendation": recommendation}


def save_diagnosis_note(phase: str, note: str) -> dict:
    """Persist a short progress note for the current diagnosis phase so the
    conversation can be resumed later."""
    from pathlib import Path

    path = Path(__file__).parent / "diagnosis_notes.jsonl"
    with path.open("a", encoding="utf-8") as f:
        import json as _json

        f.write(_json.dumps({"phase": phase, "note": note}) + "\n")
    return {"saved": True, "phase": phase}


def lookup_tool_info(tool_name: str) -> dict:
    """Look up a short description of a specific named AI/automation tool
    from a small local catalog (Zapier, n8n, Make, etc.)."""
    catalog = {
        "zapier": "No-code automation platform connecting apps via triggers and actions.",
        "n8n": "Open-source, self-hostable workflow automation tool.",
        "make": "Visual no-code automation platform (formerly Integromat).",
    }
    key = tool_name.lower().strip()
    return {"tool_name": tool_name, "description": catalog.get(key, "not found in local catalog")}


def estimate_pricing_tier(monthly_active_users: int) -> dict:
    """Estimate which pricing tier a workflow's usage volume falls into,
    based on monthly active users."""
    if monthly_active_users < 100:
        tier = "free"
    elif monthly_active_users < 1000:
        tier = "starter"
    else:
        tier = "growth"
    return {"tier": tier, "monthly_active_users": monthly_active_users}


EXTRA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "score_workflow",
            "description": (
                "Score a candidate workflow on 5 factors (frequency, pain, "
                "access, ai_fit, speed - each 1-5) to decide if it's worth "
                "piloting. Use this when the user is comparing or ranking "
                "multiple workflow ideas, not for a single already-chosen "
                "workflow's time savings.\n"
                "Example: frequency=4, pain=5, access=4, ai_fit=4, speed=3 "
                "-> {'total_score': 20, 'recommendation': 'strong candidate...'}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "frequency": {"type": "integer", "description": "How often the task repeats, 1-5"},
                    "pain": {"type": "integer", "description": "How painful/costly the task is, 1-5"},
                    "access": {"type": "integer", "description": "How easy it is to reach real users of this workflow, 1-5"},
                    "ai_fit": {"type": "integer", "description": "How well AI fits this task, 1-5"},
                    "speed": {"type": "integer", "description": "How fast a proof could be built, 1-5"},
                },
                "required": ["frequency", "pain", "access", "ai_fit", "speed"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_diagnosis_note",
            "description": (
                "Save a short note about progress in a specific diagnosis "
                "phase, so the session can resume later. Use this when the "
                "user explicitly asks to save/record their progress.\n"
                "Example: phase='hypothesis', note='drafted first version, "
                "needs a measurable result clause' -> {'saved': True}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phase": {"type": "string", "description": "One of: observation, subject, evidence, causal_chain, hypothesis, stress_test, mvp_plan"},
                    "note": {"type": "string", "description": "The note text to save"},
                },
                "required": ["phase", "note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_tool_info",
            "description": (
                "Look up information about a specific AI or automation "
                "tool or platform by name, such as what it does or how it "
                "works. Use this to find out about tools, platforms, or "
                "software.\n"
                "Example: tool_name='Zapier' -> {'description': 'No-code "
                "automation platform...'}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Name of the tool/platform, e.g. 'n8n'"},
                },
                "required": ["tool_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_pricing_tier",
            "description": (
                "Estimate which pricing tier applies based on monthly "
                "active users of a workflow or product. Use this to "
                "estimate costs or pricing for a workflow at scale.\n"
                "Example: monthly_active_users=500 -> {'tier': 'starter'}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "monthly_active_users": {"type": "integer", "description": "Expected monthly active users, e.g. 500"},
                },
                "required": ["monthly_active_users"],
            },
        },
    },
]

ALL_TOOLS = BASE_TOOLS + EXTRA_TOOLS

ALL_TOOL_FUNCTIONS = dict(TOOL_FUNCTIONS)
ALL_TOOL_FUNCTIONS.update(
    {
        "score_workflow": score_workflow,
        "save_diagnosis_note": save_diagnosis_note,
        "lookup_tool_info": lookup_tool_info,
        "estimate_pricing_tier": estimate_pricing_tier,
    }
)
