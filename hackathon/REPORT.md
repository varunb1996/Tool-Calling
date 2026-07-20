# The Token Optimization Hackathon — Track B: Aarav's Diagnoser

Repo: https://github.com/varunb1996/Tool-Calling

## What changed

Starting from the working diagnoser (Rep 2/3 of the tool-calling practice
set), per the hackathon instructions:

1. `search_web`'s `max_results` bumped 5 → 100
2. Two new tools added: `search_gmail`, `search_calendar` — backed by a
   synthetic 2-year inbox (248 emails) and calendar (190 events), since
   this used synthetic rather than real-OAuth data (see
   [diagnoser/rag/data/gen_synthetic_data.py](../diagnoser/rag/data/gen_synthetic_data.py))
3. Naive versions of all three tools built first, deliberately wasteful —
   [diagnoser/tools_naive.py](../diagnoser/tools_naive.py) — to get a real
   BEFORE number, not a guessed one
4. A full chunk → index → filter → pre-aggregate pipeline built on top —
   [diagnoser/rag/](../diagnoser/rag/) — and wired back in behind the
   *same* three tool names, so the model-facing contract never changes

## BEFORE — naive tools, one representative query

Query given to the diagnoser: *"Search my email and calendar for anything
related to the Q3 reporting automation project over the last year, and
check the web for current no-code tools I could use — I need to scope my
build brief."*

| Tool | What it did | Tokens |
|---|---|---|
| `search_gmail` (naive) | ignored the query, returned all 248 emails, full body | 24,986 |
| `search_calendar` (naive) | ignored the query, returned all 190 events | 12,661 |
| `search_web` (naive, max_results=100) | 24 results returned, full untruncated content each | 7,727 |
| **Total tool output** | | **45,374** |
| **Total payload** (+ system prompt + user query) | | **45,964** |

Full numbers: [before_results.json](before_results.json). Reproduce with
`python -m hackathon.measure_before`.

## The pipeline

**Chunk** ([diagnoser/rag/chunk_data.py](../diagnoser/rag/chunk_data.py)) —
partition Gmail/Calendar by year (same seam the lecture used for weather
data). 6 chunks total. Completeness verified by record-ID set equality,
not token-count equality — splitting one JSON array into several changes
bracket/comma overhead by a couple of tokens even with byte-identical
records, so a strict token-sum assert would have been a false alarm, not
a real bug. Caught this while writing the check, not before.

**Index** ([diagnoser/rag/build_index.py](../diagnoser/rag/build_index.py),
[diagnoser/rag/index.json](../diagnoser/rag/index.json)) — one entry per
chunk: `chunk_id`, `source`, `year`, `date_range`, `record_count`,
`labels`, `participants`, `token_count`, `path`. The whole index is 831
tokens — small enough that reading it first, before opening any chunk, is
nearly free.

**Retrieve + pre-aggregate**
([diagnoser/rag/retrieve.py](../diagnoser/rag/retrieve.py)) — keyword-only
(no embeddings, per the lecture's gate):
1. index-level filter: only open chunks whose labels overlap the query's
   keywords
2. record-level filter within opened chunks: same keyword-overlap check
   against each record's subject/labels
3. pre-aggregate: return `{date, who, subject, snippet}` instead of full
   email bodies / event descriptions
4. for `search_web`: still call Tavily with `max_results=100` (nothing to
   pre-chunk for a live API), but rank all 100 by keyword overlap with the
   query and keep only the top 5, each truncated to a 300-char snippet

**The missing-key moment:** first version of the keyword filter matched
on *any single* overlapping keyword. That over-matched — a query for "Q3
reporting automation" pulled in 33 emails instead of the real 28, because
an AI-newsletter noise email happened to contain the word "automation" on
its own. Fixed by requiring at least 2 overlapping keywords when the
query has 2+ (see the comment on `_overlap_threshold` in retrieve.py).
This is the same lesson the lecture's "missing month" story teaches, just
found from the opposite direction — too loose a filter instead of too
narrow a chunk.

## AFTER — same query, RAG-optimized tools

| Tool | What it did | Tokens |
|---|---|---|
| `search_gmail` (RAG) | opened only `gmail_2025`, matched exactly 28/28 real project emails | 1,959 |
| `search_calendar` (RAG) | opened only `calendar_2025`, matched exactly 10/10 real project events | 788 |
| `search_web` (RAG) | top 5 of 100 results by keyword relevance, snippets only | 585 |
| **Total tool output** | | **3,332** |
| **Total payload** | | **3,922** |

Full numbers: [after_results.json](after_results.json). Reproduce with
`python -m hackathon.measure_after`.

## Reduction factor

- Tool output: 45,374 → 3,332 tokens = **13.6x compression**
- Full payload: 45,964 → 3,922 tokens = **11.7x compression**

Retrieval precision was exact on the synthetic data: every real
project record was found (28/28 emails, 10/10 events), zero false
positives, and only the correct year's chunk was ever opened for either
source.

## Cost projection

Groq's `llama-3.3-70b-versatile`: $0.59 / million tokens.

| | BEFORE (45,964 tok) | AFTER (3,922 tok) |
|---|---|---|
| Per query | $0.02712 | $0.00231 |

**Scenario 1 — realistic actual usage.** The diagnoser's own design is
occasional, not daily: someone runs a multi-tool diagnosis query a
handful of times while scoping one workflow, not every day. Estimate:
500 users × 3 such queries each over a course = 1,500 queries, one-time.

| | BEFORE | AFTER | Savings |
|---|---|---|---|
| Total (one-time) | $40.68 | $3.47 | $37.21 |

**Verdict: does not clear the volume bar.** ~$37 doesn't justify the
engineering time this pipeline took, on its own — matching the lecture's
own rule ("if it runs [rarely], do not optimize it").

**Scenario 2 — if it ran daily.** The lecture's other test case: what if
usage were daily/multi-user instead? 500 active users × 1 such query/day:

| | BEFORE | AFTER | Savings |
|---|---|---|---|
| Daily | $13.56 | $1.16 | $12.40 |
| Monthly | $406.78 | $34.71 | $372.07 |
| Yearly | $4,949.17 | $422.30 | **$4,526.87** |

**Verdict: clears the bar.** At daily-active-use volume the savings
justify the work, and the case gets stronger than the dollar figure
alone suggests: our synthetic inbox is only 248 emails over 2 years. A
real inbox is easily 10-100x that. The naive tool doesn't just get more
*expensive* as that grows — at some point (as our own Rep 3 already
half-discovered and the RAG lecture's Step 0 fully demonstrated with the
weather API) it stops being a cost problem and becomes a hard 400/context-
overflow failure. The honest verdict on this pipeline: not worth building
for how the diagnoser is used *today*, clearly worth having *before* it's
used at real inbox scale.

## Deliverables checklist

- [x] App + repo link: this repo, `diagnoser/` (modified) + `diagnoser/rag/` (new)
- [x] BEFORE number: 45,964 tokens ([before_results.json](before_results.json))
- [x] AFTER number + reduction factor: 3,922 tokens, 11.7x payload / 13.6x tool-output ([after_results.json](after_results.json))
- [x] Index design: [diagnoser/rag/index.json](../diagnoser/rag/index.json), metadata keys above, missing-key story above
- [x] Cost projection: both scenarios above, explicit volume-bar verdict
