# LLM auction harness

All commands run from the repository root. Offline commands need neither an API
key nor OpenAI/Modal packages. No model calls happen at import time.

```powershell
.venv/Scripts/python experiments/run_llm.py --run smoke_fake --smoke --dry-run --quick --deviation-cohort smoke --deviation-reason "Offline three-round check"
.venv/Scripts/python experiments/run_llm.py --run smoke_live --smoke --models qwen-9b --endpoint qwen-9b=https://YOUR-ENDPOINT --max-calls 1000
```

The smoke mode enforces one N0 market and one model. The default market has 200
rounds; `--quick` uses three. Add `--gpu-hourly-usd YOUR_ACTUAL_RATE` for an
estimated dollar cost. Client wall time includes cold start; the estimate omits
idle billing and assumes a single endpoint/GPU. Fake timings and token counts
are explicitly labelled and cannot predict live performance.

`experiments/manifests/collection_v1.json` declares collection scope. Prefer
`--entry mixed.C1-XX`, for example, to read models, strength roles, market counts
and rounds from that file. `--models` takes four keys in strong_0, strong_1,
fringe_0, fringe_1 order, with one `--endpoint MODEL=URL` per distinct model.
Undeclared models, conditions, indices, seeds, policies and round extensions
are refused before submission, including in fake mode. Explicit exploratory
runs require `--deviation-cohort NAME --deviation-reason "REASON"`; outputs then
use `<run>__deviation_NAME` and record the reason. Quick mode also needs a deviation.

`collection.assignment_for` resolves physical seats and displayed labels from
the market index. Separate seeded six-pair cycles balance strong seats and
strong displayed labels; adjacent complementary pairs give each seat/label ten
strong appearances over indices 0-19. Models follow strength roles; paired
controls reuse the exact assignment. `--cartel-position` selects strong_strong,
strong_fringe or fringe_fringe, subject to the declared cell. E1 uses strong_0
as receiver and strong_1 as victim; P0 scripts both strong seats. Every market
saves the complete assignment privately. P0 applies the existing lower-cost
member/strict-cover policy to its own live costs and completed public history.
Costs and ties match `games.auction` for the resolved strength assignment and
depend only on seed and market index. They preserve prefixes when rounds grow.

Calls per round before retries/cache hits: N0/D/C2/E1: four; P0: two; C1/M2:
six. Invalid JSON gets one retry with fresh randomness; then the bid or message
is missing. No valid bids means no winner and zero profits.

## Persistence and spending

`results/raw/<run>/` contains the private configuration and a JSON audit record
per submission, plus cache-hit records. `results/raw/response_cache.sqlite3`
is the shared durable request ledger and cache. `results/llm/<run>/` contains
round-atomic `market_00000.json` checkpoints, a numeric summary and a bid figure.
Missing bids/messages are JSON null; no winner is -1. The `invalid` and
`message_invalid` arrays mark terminal failures; `complete_round_mask` marks
rounds with all four bids valid. Raw logs retain every
invalid attempt, response envelope, token count and decoding parameter.

Repeat the identical command to resume. If declared, increase `--rounds` to continue existing
games with the same cost and tie streams (for example 200 to 300). Add indices
with `--market-start 20 --markets 20` in the same run directory. The current
provisional manifest declares indices 0-19 and no round extensions; a deviation
can exercise extension now. Declare future extensions before freezing: changing
the manifest hash requires a new run. Round counts
cannot decrease. Models, seats, seed, role configuration, prompt version,
sampling and endpoint identity remain immutable within a run.

`--max-calls` is an absolute per-run cap,
persisted across restarts and counting transport attempts as well as validation
retries. Increase it explicitly to continue after a budget stop. Cache hits do
not consume it. A changed science configuration requires a new run ID. An OS
lock prevents two processes writing the same run simultaneously. Exit code 2
means stopped/incomplete/invalid; inspect the status in the summary/checkpoint.

Only definitely unsent connection failures and explicit HTTP 429 rejections
retry automatically, with bounded exponential backoff. Lost replies, server
errors, cancellations and crashes after reservation are ambiguous and block
resubmission of that request. Without server-side idempotency or provider
reconciliation, a client cannot guarantee both completion and exactly-once
billing in this situation. This harness preserves the ledger and stops. Do not
delete pending entries or move to another cache to bypass the stop. The ledger
must remain available across reruns; it is intentionally gitignored.

Live auth uses `MODAL_PROXY_TOKEN_ID` and `MODAL_PROXY_TOKEN_SECRET` in the
environment, then `.env` or `tokens.env` in the current folder or its parents.
The loader reads only those two names and credentials are never put in request bodies,
cache keys, logs or error text. Endpoint URLs must not contain credentials.

## Judges and frozen contexts

```powershell
.venv/Scripts/python experiments/judge.py results/llm/pilot_qwen9b_v3/N0/market_00000.json --run judge_L1 --level L1 --endpoint qwen-9b=https://YOUR-JUDGE-ENDPOINT
.venv/Scripts/python experiments/run_llm.py --run replay --probe frozen --source-call PATH_TO_BID_LOG --probe-draws 10 --dry-run --deviation-cohort probes --deviation-reason "Offline context-grid development"
.venv/Scripts/python experiments/run_llm.py --run intervention --probe partner-cost --source-call PATH_TO_RECIPIENT_BID_LOG --partner-call PATH_TO_PARTNER_MESSAGE_LOG --partner-cost 2 --probe-draws 10 --dry-run --deviation-cohort probes --deviation-reason "Offline intervention check"
```

Judge L1 sees only complete-round bids/winners and original round numbers;
L2 adds costs. Displayed labels determine columns and pair identities. Neither includes private
messages, roles, models, condition names or strength/pair labels. The default
judge is Qwen-9B with thinking enabled. Each probability is independently in
[0, 1]; the six values need not sum to one. Raw probabilities are pair scores;
failures (including no complete rounds) remain failures. The thinking judge has
a 12,000-token completion limit, as specified in the pre-registration draft.
Validation permits only
two answers, never selecting among valid judgements. The Gemma spot check is
preselected as core.N0 indices 0-9 at both levels. The declared probe grid uses
C1-SS markets 0-9, rounds 110,120,...,200 and both cartel members. For each cost
1,2,3 it regenerates one partner message and takes five bid draws: 3,600 calls
before invalid-answer retries. Use `--entry core.probes --probe partner-cost
--probe-draws 5` and the original source bid/partner-message logs. Other probe
modes or grids require explicit deviations. Missing contexts are not replaced.

Prompts use version 3. The neutral role is exactly `Maximise your own profit.`
Every raw call, including warm-up, judge, cache hits and probes, records the
prompt version and sampling; both participate in the response-cache key.
Vendor recipes are defined in `sampling.py`. Qwen bidders use T=0.7, Gemma
T=1.0 and Ministral T=0.15. Qwen and Gemma explicitly switch thinking off for
bidders and on for judges; Ministral has no switch. The HTTP adapter merges
OpenAI-style `extra_body` parameters into the wire JSON. An empty thought block
before JSON is accepted; nonempty reasoning in the answer is not silently removed.

Frozen probes preserve the logged request and change its seed. Honest-reference
probes rebuild the same observation with the honest role and remove the private
channel/informant. The caller can randomise swaps using the seeded draws. A
partner-cost intervention regenerates the partner message from the simultaneous
message-step context with a counterfactual own cost; it freezes public history,
the recipient's own cost and its sent message. It then re-queries the recipient
with that generated message. Missing messages stay missing. Each draw is
checkpointed and repeated commands reuse the cache.

## Pilot: first retained data chunk

```powershell
.venv/Scripts/python experiments/run_llm.py --run pilot_qwen9b_v3 --pilot --endpoint qwen-9b=https://YOUR-ENDPOINT --concurrency 128 --max-calls 26000 --max-minutes 75 --max-p95-seconds 60 --warmup-timeout 1200
```

The pilot runs N0 and P0 for indices 0-19 on the same Qwen-9B endpoint. A
long-timeout warm-up reply must arrive before any markets start. All 40 markets
then run concurrently, with at most 128 requests in flight (about 120 usable
slots: 80 N0 bidders and 40 P0 LLM bidders). `--market-concurrency` can limit
the active markets. The P0 pair follows each market's strong seats. For an
offline full-scope run, replace the endpoint flag with `--dry-run`. A short
`--pilot --dry-run --quick` run needs an explicit deviation cohort and reason.

The nominal first chunk needs 24,000 market calls and one warm-up before
retries/cache hits. Forty first-round fringe calls are identical across N0/P0
and share cached replies, so at most 23,961 submissions are needed on a fresh
cache without retries; more matching requests can reduce this further.

From round 10, gates continuously check unique-answer invalid rate >5%,
transport errors / backend attempts >2%, any strong/fringe LLM type having
only one bid value across all its valid observations, and completed-call p95
latency above `--max-p95-seconds` (default 60). Invalid rates include the
validation retry; histograms omit scripted bids. Call and active wall budgets
apply from startup and persist across resumes. Increase a cap explicitly to
continue; downtime is excluded. Stops prevent new submissions and drain
already-dispatched calls, so final wall time can exceed the dispatch deadline
by the duration of in-flight requests. Ambiguous replies retain the same
fail-closed behaviour as ordinary runs.

The pilot prints only operational metrics and the design-based projection
table. It never computes detector scores, profit comparisons or cartel success.
Compact game data remain available for analysis after preregistration:

- `results/raw/<run>/config.json`, `reproducibility.json`, `calls/*.json`, `pilot_progress.json`, `run.lock`.
- Shared ledger/cache: `results/raw/response_cache.sqlite3` (plus SQLite journal files).
- `results/llm/<run>/{N0,P0}/market_00000.json` through `market_00019.json`.
- `results/llm/<run>/pilot_report.json`, `operations.png`, `projection.json`,
  `projection.csv`, `projection_blocks.csv`.

Warm-up latency is reported separately; loaded throughput, latency and token
counts exclude warm-ups and response-cache hits. Server-reported cached prompt
tokens are retained separately. A completed repeated scope makes no new calls;
an extension or new index batch performs one new warm-up. A crash after a
committed warm-up reply recovers that reply, then checks readiness afresh;
an uncertain warm-up cannot be bypassed.

The projection covers the provisional PLAN v4 blocks, including this pilot:
280 markets, both judge levels, a Gemma judge spot check on 10 markets, and a
declared grid of 3,600 probe calls (`--projection-probe-calls` overrides the
projection only; it cannot authorise extra probe collection).
It uses A10=$1.10/h and L40S=$1.95/h, scaling time per call by nominal parameter
count / 9 and assuming equal GPU efficiency. Gemma E4B uses 4B as a scaling
proxy. Judge calls default to 10 times bidder work (`--judge-work-factor`).
These assumptions, unmeasured message/judge work and omitted idle/cold-start
billing are printed. Per-condition/model rows, per-block totals and the grand
total are saved. Fake-backend projections are labelled as illustrations and
must not be used to authorise spending.

`reproducibility.json` contains the collection content/hash, verbatim prompt
and role templates/hashes, sampling/thinking/token/retry settings, seed
derivation, installed package versions and a hash of local `pip freeze --all`.
Cloud declarations are parsed as AST literals without importing Modal: pinned
model repos/revisions, GPUs, context/batch limits and configured vLLM version.
Warm-up additionally probes authenticated `GET /version`; an unavailable route
uses the configured version with explicit provenance. A configured model pin
is recorded as configuration, not claimed as server attestation.
