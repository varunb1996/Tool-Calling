# Rep 3 — Failure Log & Routing Threshold

Method: a fixed battery of test queries, each with one obviously-correct
tool, run against a growing tool set (2 → 6 tools: `search_web`,
`estimate_time_saved`, `score_workflow`, `save_diagnosis_note`,
`lookup_tool_info`, `estimate_pricing_tier`), all with `tool_choice="auto"`
and only the first tool call inspected per query. Full raw run:
[threshold_run_log.txt](threshold_run_log.txt).

`lookup_tool_info` was deliberately written to semantically overlap with
`search_web` ("look up information about a tool/platform" vs. "search the
web for current information") specifically to try to induce a
wrong-tool-pick. The run was cut short by Groq's daily token quota
(100,000 TPD) partway into the 6-tool stage — noted honestly below rather
than papered over.

## Results by stage

| Tools in context | Queries run | Misroutes | Error rate |
|---|---|---|---|
| 2 (search_web, estimate_time_saved) | 6 | 0 | 0% |
| 3 (+ score_workflow) | 8 | 2 | 25% |
| 4 (+ save_diagnosis_note) | 10 | 0 | 0% |
| 5 (+ lookup_tool_info) | 12 | 3 | 25% |
| 6 (+ estimate_pricing_tier), partial | 2 of 12 planned | 2 | 100% (n=2 before rate-limited) |

## Every misroute, in detail

All 7 misroutes across the whole run were the **same failure type** —
none were a case of the model confidently picking the *wrong* tool from
the menu:

| Query | Expected | What happened | Stage(s) it occurred |
|---|---|---|---|
| "What's the newest AI agent framework people are using in 2026?" | `search_web` | Model emitted `<function=search_web{...}</function>` — a tag-style syntax, not the required tool-call JSON structure. Groq's API rejected it server-side with `tool_use_failed` (400) before it ever reached our code. | 3, 5, 6 tools |
| "What's the going rate for a Tavily subscription right now?" | `search_web` | Same malformed-generation failure. | 3, 5 tools |
| "What's the current pricing for the Claude API right now?" | `search_web` | Same malformed-generation failure. | 5, 6 tools |

Every single misroute was a `search_web` call and every single one was
this same generation-format failure — not one selection error occurred
anywhere in the run, including on the two `lookup_tool_info` queries at
the 5-tool stage, which I'd specifically engineered to be confusable with
`search_web`. That deliberate trap didn't spring; something else did.

## Where the threshold actually is

Not where I expected it. I went in assuming the failure would be **wrong
tool selected** as tool count/overlap grew (that's what `lookup_tool_info`
was built to test), and the routing decision itself stayed accurate at
every stage, even at 5 tools with a genuinely ambiguous pair in the mix.

What actually broke, starting between 2 and 3 tools and never at exactly
2, was **valid tool-call generation for `search_web` specifically**. The
error rate wasn't monotonic (0% → 25% → 0% → 25% → 100% on n=2) — that
non-monotonicity is itself informative: this looks like sampling
variance crossing a reliability line, not a hard, deterministic cutoff.
With only 2 tools registered, `search_web`'s call was clean every time (6/6).
The moment a 3rd tool entered the schema list, `search_web` calls started
intermittently coming out as `<function=name{...}</function>` instead of
proper JSON — and it was *only ever* `search_web` that failed this way,
never `estimate_time_saved`, `score_workflow`, `save_diagnosis_note`, or
`lookup_tool_info`.

## Routing hypothesis

`search_web` has the simplest possible parameter schema — one string
field, `query` — which makes its call shape look the most like natural
free-text generation of any tool in the set (compare to
`estimate_time_saved`'s three typed numeric fields, which force a more
rigid, JSON-like structure the model seems to lock onto reliably). My
hypothesis: once the model has multiple competing tool schemas to
attend to in the same request, the *loosest*-shaped tool is the one most
likely to have its call generation drift into a different serialization
habit (the `<function=name{...}</function>` tag format looks like a
tool-calling convention from a different training template leaking
through). Tool count alone isn't the threshold variable — **schema
rigidity of the specific tool being called** is at least as important,
and this is exactly the same "one stray character breaks a deterministic
parser" failure mode from the Rep 1 trace, just surfacing at the
API-validation layer instead of our own `json.loads`. `agent.py`'s
retry-on-`BadRequestError` loop (added after this exact failure first
appeared while generating the Rep 2 before/after proof) is a mitigation,
not a fix — it costs a retried request rather than solving the underlying
generation reliability problem.

## Caveats

- n=1 run per query per stage; LLM sampling means these exact numbers
  won't exactly reproduce. The *pattern* (malformed `search_web` calls
  appearing once ≥3 tools are registered, and only for `search_web`) is
  the finding, not the precise percentages.
- The 6-tool stage never finished (Groq free-tier daily quota), so the
  top of the range is unconfirmed — what's documented is where the
  failure *starts*, not where it plateaus.
