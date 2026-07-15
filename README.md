# Make the Diagnoser Stop Lying — Tool Calling Practice Set

100xEngineers LLM Deep Dive · Tool Calling Practical.

Traces how an LLM hands work to a deterministic tool without breaking it
(Rep 1), implements that handover for real by connecting Aarav's workflow
diagnoser to Tavily web search (Rep 2), then deliberately pushes the tool
set further to find where `tool_choice="auto"` routing starts breaking
(Rep 3).

## Structure

```
├── requirements.txt          # groq, tavily-python, anthropic, python-dotenv
├── .env.example              # copy to .env and fill in your keys
├── rep1_trace/
│   ├── capture_trace.py      # captures one real tool call end-to-end
│   ├── captured_trace.json   # raw request/response payloads from that run
│   └── trace.md              # Rep 1 deliverable: the written trace
├── diagnoser/
│   ├── tools.py               # search_web, estimate_time_saved + Rep 3 tools, JSON specs
│   ├── system_prompt.py       # the diagnoser's 7-phase coaching system prompt
│   ├── agent.py                # the tool-calling loop (tools=tools, tool_choice="auto", run_tools)
│   └── cli.py                  # interactive REPL: python -m diagnoser.cli
├── outputs/
│   ├── generate_before_after.py
│   ├── before_after.md         # Rep 2 deliverable: hallucination vs. grounded answer
│   ├── threshold_test.py       # Rep 3: runs a query battery against a growing tool set
│   ├── threshold_run_log.txt   # raw run output
│   └── failure_log.md          # Rep 3 deliverable: misroutes, threshold, hypothesis
├── tool_specs.json            # final JSON tool specs, standalone
└── SUBMISSION.md              # checklist-to-file mapping
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in GROQ_API_KEY and TAVILY_API_KEY
```

- **Groq** (Llama 3.3, used for the diagnoser and both traces): console.groq.com → API Keys
- **Tavily** (used by the `search_web` tool): app.tavily.com → API Keys, free tier, no card

## Running it

```bash
# Rep 1 — capture a real tool-calling trace
python rep1_trace/capture_trace.py

# Rep 2 — talk to the diagnoser interactively
python -m diagnoser.cli

# Rep 2 — regenerate the hallucination vs. grounded before/after proof
python -m outputs.generate_before_after

# Rep 3 — run the tool-routing threshold experiment
python -m outputs.threshold_test
```

## Submission Checklist

| Requirement | Where it is |
|---|---|
| Rep 1 trace document (one page, own words, real payloads) | [rep1_trace/trace.md](rep1_trace/trace.md), raw payloads in [rep1_trace/captured_trace.json](rep1_trace/captured_trace.json) |
| Repo link or notebook for Rep 2, with before/after outputs saved | This repo — https://github.com/varunb1996/Tool-Calling — plus [outputs/before_after.md](outputs/before_after.md) |
| Rewritten system prompt and tool descriptions (JSON) | [diagnoser/system_prompt.py](diagnoser/system_prompt.py), [tool_specs.json](tool_specs.json) |
| Rep 3 failure log with the threshold found and routing hypothesis | [outputs/failure_log.md](outputs/failure_log.md), raw run in [outputs/threshold_run_log.txt](outputs/threshold_run_log.txt) |
| One sentence: the boundary I got wrong this week, and the spec that fixed it | See [SUBMISSION.md](SUBMISSION.md#the-boundary-i-got-wrong-this-week) |

### Notable findings

- **Rep 1:** traced Groq (Llama 3.3) instead of GPT/Claude/Gemini — same
  OpenAI-compatible `tools`/`tool_calls`/`role:"tool"` wire format, so the
  mechanism traced is the same; only the model differs.
- **Rep 2:** without `search_web`, the model confidently invented "Claude
  2.1, $12/million tokens"; with it wired in, it correctly reported the
  real current Claude Opus 4.8 pricing via an actual Tavily search.
- **Rep 3:** a tool deliberately built to overlap with `search_web`
  (`lookup_tool_info`) never caused a wrong-tool pick. What broke instead,
  once 3+ tools were registered, was `search_web` intermittently emitting
  a malformed (non-JSON) tool call — the same "one stray character breaks
  a deterministic parser" failure from Rep 1, surfacing at the API's own
  validation layer as a `tool_use_failed` 400.

See [SUBMISSION.md](SUBMISSION.md) for the full checklist mapping and
[outputs/failure_log.md](outputs/failure_log.md) for the complete Rep 3
analysis.
