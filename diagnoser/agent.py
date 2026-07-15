"""
The tool-calling loop itself.

Three moving parts, matching the Rep 1 trace exactly:
1. completions call - we pass `tools=tools` as its OWN parameter and
   `tool_choice="auto"` (never embed tool definitions inside the system
   prompt - the model treats `tools` as a structured contract, not text
   it can paraphrase away).
2. the model's decision - it comes back as `message.tool_calls`, a list of
   {id, function: {name, arguments}} - `arguments` is a JSON *string* the
   model generated, not a dict, which is exactly the fragile point Rep 1's
   trace is about.
3. run_tools - WE parse that JSON, validate it, run the real Python
   function, and append a `role: "tool"` message keyed by the same
   `tool_call_id` so the model can match its request to our answer.
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq, BadRequestError

from diagnoser.system_prompt import DIAGNOSER_SYSTEM_PROMPT
from diagnoser.tools import BASE_TOOLS, TOOL_FUNCTIONS

load_dotenv()

MODEL = "llama-3.3-70b-versatile"

_client = None


def get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def run_tools(tool_calls, tool_functions, log=None):
    """Execute every tool call the model requested and return the
    role:tool messages to append to the conversation.

    `log` is an optional list that (name_called, args, error_or_None)
    tuples get appended to - used by the Rep 3 threshold test to record
    routing behaviour without duplicating this function.
    """
    tool_messages = []
    for call in tool_calls:
        name = call.function.name
        raw_args = call.function.arguments
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            # This is the exact failure mode Rep 1 ends on: the model emitted
            # text that looks like JSON but a stray quote/comma broke the
            # parser. We surface it as a tool error instead of crashing, so
            # the model gets a chance to retry with corrected arguments.
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps({"error": f"invalid JSON arguments: {e}"}),
                }
            )
            if log is not None:
                log.append((name, raw_args, f"json_decode_error: {e}"))
            continue

        func = tool_functions.get(name)
        if func is None:
            # The model asked for a tool name that doesn't exist in our
            # registry at all - never silently ignore this, always report it
            # back explicitly.
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps({"error": f"unknown tool: {name}"}),
                }
            )
            if log is not None:
                log.append((name, raw_args, "unknown_tool"))
            continue

        try:
            result = func(**args)
            error = None
        except Exception as e:  # boundary: never let a bad tool arg crash the loop
            result = {"error": str(e)}
            error = str(e)

        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            }
        )
        if log is not None:
            log.append((name, args, error))

    return tool_messages


def chat(
    messages,
    tools=None,
    tool_functions=None,
    system_prompt=DIAGNOSER_SYSTEM_PROMPT,
    max_rounds=4,
    log=None,
):
    """Run the full request -> tool-call -> tool-result -> final-answer
    cycle, looping in case the model chains multiple tool calls.

    messages: prior conversation as a list of {"role", "content"} dicts,
    NOT including the system prompt.
    tools/tool_functions: defaults to Rep 2's search_web + estimate_time_saved.
    Returns (final_assistant_text, full_messages_including_system).
    """
    tools = BASE_TOOLS if tools is None else tools
    tool_functions = TOOL_FUNCTIONS if tool_functions is None else tool_functions

    client = get_client()
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    for _ in range(max_rounds):
        # tool_use_failed: the server-side decoder itself rejected the
        # model's generation because it didn't come out as valid tool-call
        # JSON (e.g. it emitted `<function=name{...}</function>` instead of
        # the proper structure). This is the same "one stray character
        # breaks a deterministic parser" failure from the Rep 1 trace, just
        # caught one layer further upstream, by Groq's API instead of our
        # own json.loads. There's no code fix for a bad generation - the
        # only lever is to retry and hope the resample comes out clean.
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=full_messages,
                    tools=tools,
                    tool_choice="auto",
                )
                break
            except BadRequestError as e:
                if log is not None:
                    log.append(("<api_call>", str(e), "tool_use_failed_retry"))
                if attempt == 2:
                    return f"(model repeatedly failed to emit a valid tool call: {e})", full_messages
        choice = response.choices[0]
        message = choice.message

        full_messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls]
                if message.tool_calls
                else None,
            }
        )

        if not message.tool_calls:
            return message.content, full_messages

        tool_messages = run_tools(message.tool_calls, tool_functions, log=log)
        full_messages.extend(tool_messages)

    return "(gave up after max_rounds of tool calls)", full_messages
