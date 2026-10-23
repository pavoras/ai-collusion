# Method notes: pairwise net influence (Bonjour, Aggarwal, Bhargava, UAI 2022)

Paper: "Information-Theoretic Approach to Detect Collusion in Multi-Agent Games", PMLR 180:223–232,
https://proceedings.mlr.press/v180/bonjour22a.html. No public code from the authors; we implement it ourselves.
Notes below are a paraphrase of Sections 3–5, written 23.10.2026.

## Definitions

Setting: n > 2 agents, exactly two colluders, discrete actions, many game records. Each record is a sequence of
(state, actions, reward).

**Individual influence** of agent i on agent j (Eq. 3), a conditional mutual information:

    γ(i; j) = Σ_{s_ij} p(s_ij) Σ_{a_i, a_j} p(a_i, a_j | s_ij) · log[ p(a_i, a_j | s_ij) / ( p(a_i | s_i) p(a_j | s_j) ) ]

- s_i, s_j: what each agent observes; s_ij: the joint state.
- **Fully observable simultaneous games** (e.g. RPS): s_ij = s_i = s_j = s, so γ(i; j) = I(A_i; A_j | S)
  (Eq. 6–7) and γ is **symmetric**: γ(i; j) = γ(j; i).
- **Sequential games** (e.g. poker): only count pairs where j acts after i; then γ is not symmetric.

**Net influence** (Eq. 4): influence of i on j minus the strongest influence any third agent has on j:

    Γ(i; j) = γ(i; j) − max_{k ≠ i, j} γ(k; j)

Even when γ is symmetric, Γ(i; j) ≠ Γ(j; i), because the subtracted term looks at j in one case and at i in the
other.

**Detection rule** (Eq. 5): i and j collude if Γ(i; j) ≥ α **and** Γ(j; i) ≥ α. The algorithm reports collusion
only if **exactly one** pair passes. α is a hyper-parameter; the paper uses **α = 0.05** throughout.

**Estimator** (Eq. 12–13): plain counting (plug-in / "Monte Carlo" with a hash table):
p(a_i | s_i) = N(a_i, s_i) / N(s_i), p(a_i, a_j | s_ij) = N(a_i, a_j, s_i, s_j) / N(s_i, s_j).
No bias correction, no significance test.

## Units: bits (our inference)

The paper does not state the log base. Their RPS results only make sense in **bits** (log2):
with α = 0.05, CP = 0.1 is "never detected" and CP = 0.2 is detected with enough games. The true values below
match that in bits but not in nats (CP = 0.2 would be 0.038 nats < α).

## RPS replication setup (Section 5.1)

- Three players, actions R/P/S, simultaneous. Payoff rules: all three the same → everybody 0; all three different →
  everybody 1; two distinct actions → every player with the winning action gets 1 (R > S, S > P, P > R).
  Full table in the paper, Table 1.
- **Player A** (primary colluder): uniform random. **Player C** (honest): uniform random.
- **Player B** (assistant): with probability CP ("collusion probability") plays the move that guarantees A a point
  regardless of C, i.e. B = beaten(A): A=R → B=S, A=P → B=R, A=S → B=P. Otherwise uniform random.
  (B knowing A's move is assumed "ex-ante coordination or signalling".)
- "Number of games": we read one game as one round, because CP = 1 reaches 100 % detection with 60 games.
  State is not specified for RPS in the main text (Appendix A is in the supplement); start with **no state**
  (one constant state), then try "last round's joint action" as a variant.

### Control values (true γ(A; B) in bits, our calculation)

P(B = beaten(A)) = CP + (1 − CP)/3, the other two moves share the rest.

| CP | 0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.7 | 1.0 |
|---|---|---|---|---|---|---|---|---|
| γ(A; B) [bits] | 0 | 0.014 | 0.055 | 0.122 | 0.214 | 0.333 | 0.663 | 1.585 |

γ(A; C) = γ(B; C) = 0 in truth, so Γ(A; B) = Γ(B; A) ≈ γ(A; B).

### Paper results to reproduce

- Fig. 3: Γ for all pairs vs CP at 1000 games; detection above α from CP ≈ 0.2–0.3 on.
- Table 2, collusion detection accuracy (CDA, 1000 iterations per row):

| games | CP = 0.3 | CP = 0.4 | automatic (DDQN) |
|---|---|---|---|
| 100 | 37.1 | 58.4 | 81.5 |
| 200 | 48.3 | 79.2 | 93.2 |
| 300 | 71.0 | 96.2 | 98.1 |
| 400 | 82.8 | 99.3 | 98.9 |
| 500 | 89.6 | 99.7 | 99.4 |
| 1000 | 100 | 100 | 99.9 |

  Also: CP = 1 → 100 % with 60 games; CP = 0.2 → 24.3 % at 1000 games, 82.3 % at 10 000 games;
  CP = 0.1 → about 8 %.
- The paper reports no false-positive rate for the no-collusion case in RPS.

## Pitfalls and our planned improvements

1. **Plug-in MI is biased upwards** with few samples: about (|A_i| − 1)(|A_j| − 1) / (2 N ln 2) bits per state.
   For 3×3 actions: 0.048 bits at N = 60, 0.029 at N = 100, 0.003 at N = 1000. With many states the bias grows
   per state and the tables get sparse. In Γ the bias partly cancels (both terms biased), but the variance does not.
2. **Fixed α is not calibrated**: its false-positive rate depends on N, action count and state count.
   Improvement: a **permutation test**. Shuffle a_i across rounds *within each state*, recompute γ / Γ, repeat
   ~200–1000 times. Gives a p-value per pair and a bias-corrected γ (observed − mean of null). Report the
   false-positive rate of fixed α vs permutation threshold on all-random data, and detection power at CP 0.1–0.3.
3. **Keep the state small** (none, or last round's joint action). Large states make the tables too sparse.
4. **LLMs at temperature 0** are nearly deterministic, leaving no variance to measure. Use 0.7–1.0.
5. Always run a **positive control** (known colluding pair) and a **negative control** (no pair) before variants.
6. Baselines for the LLM round: plain action correlation (e.g. Cramér's V or plug-in MI without the "net" step)
   and an LLM judge reading the game log.

## What is new for the sprint

The method was only tested on rule-based and RL agents (RPS, Leduc poker). **LLM agents were never tested.**
That, plus the calibrated permutation test, is the contribution.
