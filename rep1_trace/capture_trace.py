"""
Rep 1 - capture a REAL tool-calling trace.

The practice set suggests GPT/Claude/Gemini specifically so the trace
isn't tied to the same provider used to build the Rep 2 diagnoser. We
used Groq (hosting Llama 3.3) instead, to avoid a second billing setup -
Groq's API is intentionally OpenAI-compatible, so the request/response
shape captured here (tools param, tool_calls, role:"tool" messages) is
the same "OpenAI-style function calling" format GPT itself uses. The
mechanism being traced is provider-agnostic; only the model differs.

This does not build anything reusable. It exists purely to observe and
print every payload that crosses the wire during one tool call, so that
trace.md can be written from real data instead of guessed data.

Run: python rep1_trace/capture_trace.py
Requires GROQ_API_KEY in .env (see .env.example).
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"

# One tool, deliberately the simplest possible pure function - no network
# call inside it - so nothing in this trace depends on a third-party API
# being up. The point is the *handover mechanism*, not the tool's logic.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "estimate_time_saved",
            "description": (
                "Calculate the hours and money saved over a period once a manual "
                "task is automated. Use this whenever the user gives a per-week "
                "time cost for a task and asks about savings, ROI, or payback "
                "from automating it."
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
    }
]


def estimate_time_saved(hours_per_week: float, weeks: int, hourly_rate: float) -> dict:
    total_hours = hours_per_week * weeks
    total_value = total_hours * hourly_rate
    return {
        "total_hours_saved": total_hours,
        "total_value_saved": total_value,
        "currency_note": "same currency as hourly_rate",
    }


def main():
    trace = {}

    messages = [
        {
            "role": "user",
            "content": (
                "I spend 5 hours a week on manual weekly reporting. If I "
                "automate it over a 6 week pilot and my hourly rate is 40, "
                "how much time and money would that save? Use the tool."
            ),
        }
    ]

    request_1 = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
    }
    trace["request_1"] = request_1
    print("=== REQUEST 1 (sent to Groq) ===")
    print(json.dumps(request_1, indent=2))

    response_1 = client.chat.completions.create(**request_1)
    response_1_dict = response_1.model_dump()
    trace["response_1"] = response_1_dict
    print("\n=== RESPONSE 1 (model's decision) ===")
    print(json.dumps(response_1_dict, indent=2, default=str))

    message_1 = response_1.choices[0].message
    tool_call = message_1.tool_calls[0]
    print(f"\n>>> Model wants to call: {tool_call.function.name}({tool_call.function.arguments})")
    print(f">>> tool_call_id: {tool_call.id}")
    print(f">>> note: arguments is a JSON STRING the model generated, not a dict yet")

    args = json.loads(tool_call.function.arguments)

    # This is the deterministic layer: OUR code decides how to execute it.
    # The model never touched a network call or a Python interpreter.
    tool_result = estimate_time_saved(**args)
    print(f">>> Parsed args: {args}")
    print(f">>> Executed locally, result: {tool_result}")

    # Hand the result back, tagged with the same tool_call_id, so the model
    # can match its request to our answer.
    messages.append(
        {
            "role": "assistant",
            "content": message_1.content,
            "tool_calls": [tc.model_dump() for tc in message_1.tool_calls],
        }
    )
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_result),
        }
    )

    request_2 = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
    }
    trace["request_2"] = request_2
    print("\n=== REQUEST 2 (tool result handed back) ===")
    print(json.dumps(request_2, indent=2, default=str))

    response_2 = client.chat.completions.create(**request_2)
    response_2_dict = response_2.model_dump()
    trace["response_2"] = response_2_dict
    print("\n=== RESPONSE 2 (final grounded answer) ===")
    print(json.dumps(response_2_dict, indent=2, default=str))

    final_text = response_2.choices[0].message.content
    print("\n=== FINAL ANSWER TEXT ===")
    print(final_text)

    out_path = Path(__file__).parent / "captured_trace.json"
    out_path.write_text(json.dumps(trace, indent=2, default=str), encoding="utf-8")
    print(f"\nFull raw trace written to {out_path}")


if __name__ == "__main__":
    main()
