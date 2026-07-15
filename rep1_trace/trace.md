# Rep 1 — How Does the Handover Actually Work?

Model used: **Llama 3.3 70B via Groq's chat completions API**, which is
deliberately OpenAI-compatible — the same `tools` / `tool_calls` /
`role: "tool"` shape that GPT uses. The mechanism traced here is not
specific to one vendor; only the model differs from what the practice set
suggested (GPT/Claude/Gemini). Raw payloads below are copied verbatim from
a real run (`rep1_trace/capture_trace.py`, saved in full to
`captured_trace.json`) — nothing here is invented.

One tool was registered: `estimate_time_saved(hours_per_week, weeks,
hourly_rate)`, a pure calculator with no network call inside it, so the
trace isolates the handover mechanism from any third-party API's own
behavior.

## Step by step

**1. The request carries the tool contract as structured data, not prose.**
`tools=tools` is its own top-level parameter in the request body, separate
from `messages`. Each tool is a JSON object: `type: "function"`, then a
`function` block with `name`, `description`, and a `parameters` JSON
Schema (`type`, `properties`, `required`). Nothing about the tool lives in
the system or user message text. This matters: if the tool spec were just
pasted into a prompt, the model could paraphrase it, forget a field, or
ignore it under pressure from other instructions. As structured data in
its own parameter, the API can enforce it's present every turn and the
model is trained to treat it as a distinct decision surface.

```json
"tools": [{
  "type": "function",
  "function": {
    "name": "estimate_time_saved",
    "description": "Calculate the hours and money saved over a period once a manual task is automated...",
    "parameters": {
      "type": "object",
      "properties": {
        "hours_per_week": {"type": "number", "description": "..."},
        "weeks": {"type": "integer", "description": "..."},
        "hourly_rate": {"type": "number", "description": "..."}
      },
      "required": ["hours_per_week", "weeks", "hourly_rate"]
    }
  }
}]
```

`tool_choice: "auto"` is the third piece: it tells the model it's allowed
to pick zero or one of the registered tools, as opposed to `"none"`
(never call) or forcing a specific one.

**2. The model doesn't call anything — it emits a decision as text.**
Given the user's message ("I spend 5 hours a week on manual weekly
reporting... how much would that save? Use the tool."), the model's
response came back with `finish_reason: "tool_calls"` and `content: null`.
Instead of an answer, `message.tool_calls` contained:

```json
{
  "id": "j4mped9yg",
  "type": "function",
  "function": {
    "name": "estimate_time_saved",
    "arguments": "{\"hourly_rate\":40,\"hours_per_week\":5,\"weeks\":6}"
  }
}
```

Two things stand out. First, `content` is `null` — when the model decides
to call a tool, it doesn't also produce a chat answer in the same turn.
Second, and critical: **`arguments` is a string**, not a JSON object. The
model generated that string one token at a time, the same way it generates
any other text. It happens to look like valid JSON because the model was
trained hard to produce exactly that shape, but structurally it is no
different from generating a sentence — there is no guarantee baked into
the generation process that the braces balance or the quotes close.

**3. Our code — not the model — executes the tool.**
The model never touched a network call, a database, or a Python
interpreter. It read text (the tools list + the conversation) and emitted
more text (a JSON-shaped string naming a function and its arguments). Our
backend is the one that:
- parses `arguments` with `json.loads` (this is where malformed JSON would
  explode if it were ever going to),
- validates/executes: `estimate_time_saved(hourly_rate=40, hours_per_week=5, weeks=6)`,
  which returned `{"total_hours_saved": 30, "total_value_saved": 1200, ...}`.

This is the deterministic boundary the whole mechanism exists to protect:
whatever the model emits, the actual multiplication and the actual API
call are ordinary, predictable Python, run by us, not "hoped into
existence" by the model.

**4. The result travels back tagged with the same call ID.**
We appended two new messages to the conversation before calling the model
again: the assistant's own `tool_calls` message (so the model has a
record of what it asked for), and a new message with `role: "tool"`,
`tool_call_id: "j4mped9yg"` (matching the original call's `id` exactly),
and `content` set to the JSON-serialized result string:

```json
{"role": "tool", "tool_call_id": "j4mped9yg",
 "content": "{\"total_hours_saved\": 30, \"total_value_saved\": 1200, ...}"}
```

The `tool_call_id` match is what lets the model correctly attribute this
result to *that specific* call, which matters the moment more than one
tool call happens in a turn — without the ID, results and requests would
have no way to line up.

**5. The second request produces the final, grounded answer.**
Same `tools` and `tool_choice: "auto"` were sent again (the model always
needs to see its available tools, every turn, since nothing is
remembered from the API's side between calls). This time `finish_reason`
was `"stop"`, `tool_calls` was `null`, and `content` was a real sentence:
*"...automating the manual weekly reporting task over a 6-week pilot
period would save 30 hours of time and $1200 in labor costs..."* — built
entirely from the number our Python function actually returned, not from
the model's own arithmetic.

## Does this mechanism guarantee the API won't break?

Partially, and only on one side of the boundary. The `tools`/`parameters`
schema constrains what the model is *steered* to produce, and providers
run their own decoding constraints to keep the JSON well-formed most of
the time — but `arguments` is still fundamentally generated text. Nothing
stops a single stray quote, an unescaped character inside a string value,
or a truncated response (e.g. hitting a token limit mid-argument) from
producing a string that `json.loads` cannot parse. That's the
colon-and-quotes failure mode from the lecture: the instant the model's
free-text generation has to become a deterministic API's structured
input, one broken character is enough to snap the handover. The
mechanism doesn't prevent that failure — it *isolates* it: because parsing
happens in our own code at a single well-defined point (`json.loads` on
`arguments`), a malformed payload throws a catchable, specific error right
there, instead of corrupting some downstream system silently. The
guarantee is not "this will never break," it's "when it breaks, you'll
know exactly where and why," which is why `agent.py`'s `run_tools()`
catches `json.JSONDecodeError` specifically and reports it back to the
model as a tool error rather than crashing the whole loop.
