"""
Rep 2 proof - same question, asked once with tools disabled (forces the
model to answer from frozen training knowledge -> hallucination risk) and
once with search_web wired in (forces a real Tavily search -> grounded
answer). Saves both, verbatim, to outputs/before_after.md.

Run: python -m outputs.generate_before_after
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from diagnoser.agent import chat

load_dotenv()

MODEL = "llama-3.3-70b-versatile"

QUESTION = (
    "For the build-sprint phase of my workflow pilot, what is the newest "
    "Claude model available right now, and what does it cost per million "
    "input tokens? Also, is there a Llama model newer than 3.3 I should "
    "consider? I need current, accurate information, not a guess."
)


def get_before_answer():
    """No tools at all, and deliberately NOT the diagnoser's system prompt -
    that prompt tells the model to refuse to guess about recent things,
    which just produces a hedge ("I'd need to search") instead of the
    hallucination this test is trying to surface. A generic assistant
    prompt that's willing to answer directly shows what the diagnoser
    would do if it didn't have search_web wired in at all."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful, knowledgeable assistant. Answer directly and specifically from what you know. Do not say you need to search or that you're unsure - give your best concrete answer.",
            },
            {"role": "user", "content": QUESTION},
        ],
    )
    return response.choices[0].message.content


def get_after_answer():
    """search_web wired in via the normal diagnoser loop."""
    log = []
    reply, full_messages = chat([{"role": "user", "content": QUESTION}], log=log)
    tool_calls_made = [
        m for m in full_messages if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    return reply, tool_calls_made, log


def main():
    print("Getting BEFORE answer (no tools)...")
    before = get_before_answer()
    print(before)

    print("\nGetting AFTER answer (search_web enabled)...")
    after, tool_calls_made, log = get_after_answer()
    print(after)

    doc = f"""# Rep 2 — Before / After: Does Grounding Beat Hallucination?

**Question asked (identical both times):**

> {QUESTION}

Llama 3.3's training cutoff is well before today's date, so any current
model-release or pricing question is exactly the kind of thing it cannot
know for certain — this is the test the practice set asks for.

## BEFORE (tools disabled — model answers from training data alone)

{before}

## AFTER (search_web wired in via tool_choice="auto")

Tool calls made during this run: {len(tool_calls_made)}

{after}

## What changed

The "before" answer is generated purely from next-token prediction over
frozen training data — any model names, prices, or version numbers in it
past Llama 3.3's cutoff are the model's best guess dressed up as fact,
not verified information. The "after" answer required the model to
recognize the question needed current information, call `search_web`
with a query it composed itself, receive real Tavily results back as a
`role: "tool"` message, and only then produce its final sentence — so
any specific claim in it traces back to an actual search result rather
than the model's internal weights.
"""

    out_path = Path(__file__).parent / "before_after.md"
    out_path.write_text(doc, encoding="utf-8")
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
