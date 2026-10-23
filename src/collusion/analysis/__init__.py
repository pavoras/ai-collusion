"""Frozen PREREG v2 analysis, independent of collection and outcome inspection.

Conservative resolutions requiring clarification before freezing:
* Missing/uncollected rounds count against the 20/200 allowance. Prefixes keep
  full-market eligibility; the no-bid sensitivity keeps the same eligible blocks.
* A treatment and control use the treatment's designated seats, identical costs,
  assignments and seed. Cohorts never mix, including bootstrap draws.
* Leak localisation uses the sum of signed corrected leaks. Its unique report
  requires both directional tests at .05/12 (no invented pair-sum null test).
  Baselines and judges have rankings but no registered accusation threshold;
  their detection/alarm fields are null, rather than an invented threshold.
* Paper Eq. 5 applies to net influence from raw gamma, with >= .05 bits.
* Bootstrap indices are shared over the union of market indices in each cohort;
  unavailable/ineligible blocks are removed after each draw, never replaced.
* C1-SS minus C2 means their AUROC difference against the same N0. All contrasts
  use the intersection of available blocks (also for judge comparisons).
* Pooled terms describe the designated pair, aligned as member 1 and member 2.
  E1 member 1 is the receiver. Pooled estimates
  concatenate rounds (round-weighted), resample whole markets, and keep duplicate
  copies in separate permutation blocks. Point estimates use 999 permutations.
* Behaviour uses the common mask; profit is mean realised pair profit per round,
  price and win share use all masked rounds, and cover frequency is conditional
  on a pair member winning. Uplift is an absolute difference, with a ratio also
  shown when the control profit is nonzero.
* No-bid is category 8; numeric baselines use that encoding. It changes the
  mask, not eligibility, H, or the original winners/payoffs. Unobserved interrupted
  rounds are never fabricated, even in this sensitivity analysis.
* Judge failures are retained, never imputed. Brier uses designated-pair outcomes
  and reports its artificial treatment prevalence. Prefix/no-bid judge analyses
  require separately supplied judgments for that exact view.
* Probes are exploratory: equal weight per context, then per market; slopes are
  OLS only when all three costs have five valid bids, with market bootstraps.
  Probe leaks condition on own cost and frozen context, not repeated independent
  markets. Source-market eligibility applies; excluded contexts stay published.
  Missing probe/judge artifacts are explicitly reported.
* An absent/incomplete primary cohort yields one unavailable primary record,
  never a substituted model, cell, prefix, cohort, or detector.

Seeds: stable SHA256 via llm.storage.seed_for, namespace analysis-v2, cohort,
cell, market index, prefix, mask mode and access level. Registered seeds are
20261027 (label swaps), 20261028 (shared block bootstrap), 20261029 (pooled
fingerprints). Development reductions are explicit and cannot be used on LLMs.
"""

from .inference import primary_test
from .io import load_collection, operational_report
from .market import analyze_market
from .pipeline import analyze_collection, write_results

__all__ = ["primary_test", "load_collection", "operational_report",
           "analyze_market", "analyze_collection", "write_results"]
