# Report outline (follows the official Apart template)

Template (fetched 23.10.2026): title, authors + affiliation ("Marvin Kemper, Independent", "With Apart Research"),
abstract 150-250 words, then sections 1-6, Code and Data, Author Contributions (optional), References, Appendix,
LLM Usage Statement. **Recommended length: 4 pages excluding references and appendix** (Intro + Related Work 1 p,
Methods + Results 2.5 p, Discussion 0.5 p). Sprint page additionally requires an appendix "Limitations and Dual-Use /
Ethical Considerations" and allows at most 8 pages. Figures and tables numbered, captions readable on their own,
placed near first reference, legible text. Consistent citation format with author, year, title, venue, URL/DOI.
The template strongly encourages that the final text is primarily written by the team (Marvin); Claude drafts
and checks, Marvin rewrites in his own words.

**Title:** Collusion, Espionage, or Look-alikes? Auditing Information Flow between LLM Agents
**Subtitle:** Pairwise net influence with and without private inputs in a procurement auction
**Research question:** Can pairwise net influence detect covert coordination between LLM agents, and when do
private inputs let an auditor tell collusion apart from espionage and shared-history dependence?

## Page budget and content

| Section | Pages | Content | Figures / tables |
|---|---|---|---|
| Abstract | - | problem, approach, key results, takeaway; written last | - |
| 1 Introduction | 0.6 | AI agents in markets; covert coordination; behaviour-based auditing reads no messages (so it does not depend on message content; we do not test steganographic channels); the confusion between collusion, espionage and look-alikes; contributions list (3) | Fig. 1 setup schematic (small) |
| 2 Related Work | 0.4 | Bonjour et al. 2022; LLM collusion in markets (Fish 2024, Agrawal 2025, Lin 2024); covert channels and audits (Motwani 2024, Audit the Whisper 2025); white-box detectors (NARCBench / multi-agent interpretability); bid-rigging screens (Huber & Imhof 2019, Imhof & Wallimann 2021, Wallimann et al. 2022); concurrent sprint work (two repos) | - |
| 3 Methods | 1.1 | Eq. 4-5; Eq. 3 and its decomposition into action and directional leak terms; permutation calibration; auction game; conditions; models; metrics; pre-registration | Table 1 conditions (compact) |
| 4 Results | 1.4 | (a) replication + calibration in one sentence and a small panel; (b) detection per condition and auditor view (hero); (c) information-flow fingerprints; (d) causal partner-cost probe; (e) robustness across labs, sizes, mixed cartels (one compact panel or table) | Fig. 2 fingerprints (hero), Fig. 3 detection/AUROC, Table 2 robustness |
| 5 Discussion and Limitations | 0.5 | what an auditor can and cannot infer; limitations (synthetic game, instructed cartels, null validity, sample size); future work | - |
| 6 Conclusion | short | 1 paragraph | - |
| Code and Data | - | repo link, results folders, logs | - |
| References | - | verified only | - |
| Appendix | free | A replication details (Table 2 comparison, calibration figure); B prompts; C scripted simulations; D all per-model results; E statistics details; F Limitations and Dual-Use / Ethical Considerations (required); G LLM usage statement | - |

Rule: a figure enters the main text only if the story needs it; everything else goes to the appendix. The appendix
always carries the single table with every registered cell (PREREG section 13), whatever the main text shows.

Appendix F (Limitations and Dual-Use / Ethical Considerations) must cover: collusion is instructed, not emergent;
synthetic procurement game, limited external validity; statistical dependence is not intent or harm; false
accusations and the need for human review; access to private costs (privacy, who may hold such data); misuse for
cartel design or detector evasion; no real procurement participants; compute spent; limits of behaviour-only
auditing against adaptive concealment; the treatment bundle (goal, partner naming, secrecy, channel) cannot be
separated.

## Related work, verified on 23.10.2026 (to cite)

- Bonjour, Aggarwal, Bhargava (2022). Information-Theoretic Approach to Detect Collusion in Multi-Agent Games. UAI,
  PMLR 180. https://proceedings.mlr.press/v180/bonjour22a.html (read: Eq. 3 uses each agent's own observed state;
  Leduc colluders see the partner's private card).
- Motwani et al. (2024). Secret Collusion among AI Agents: Multi-Agent Deception via Steganography. NeurIPS.
- Audit the Whisper: Detecting Steganographic Collusion in Multi-Agent LLMs (2025). arXiv:2510.04303 (cross-run
  mutual information, permutation invariance, auditor interventions; ColludeBench incl. first-price auctions; run-level,
  no pair identification, no private-state conditioning, no direction).
- Agrawal et al. (2025). Evaluating LLM Agent Collusion in Double Auctions. arXiv:2507.01413.
- Fish, Gonczarowski, Shorrer (2024). Algorithmic Collusion by Large Language Models. arXiv:2404.00806.
- Lin et al. (2024). Strategic Collusion of LLM Agents: Market Division in Multi-Commodity Competitions.
  arXiv:2410.00031 (title to verify).
- Faithful yet Collusive: Why Chain-of-Thought Monitoring Cannot Detect Collusion in LLM Pricing Agents (2026).
  arXiv:2609.18346 (supports behaviour-based audits; authors to verify).
- Detecting Multi-Agent Collusion Through Multi-Agent Interpretability / NARCBench (Rose et al. 2026,
  arXiv:2604.01151).
- Huber, Imhof (2019). Machine learning with screens for detecting bid-rigging cartels. Int. J. of Industrial
  Organization. Wallimann, Imhof, Huber (2022). A machine learning approach for flagging incomplete bid-rigging
  cartels. Computational Economics. Imhof, Wallimann (2021). Detecting bid-rigging coalitions ... (exact title to
  verify).
- Concurrent sprint work: Raj-Taware/collusion-net-influence, soumya-nayak-commits/collusion-sprint (GitHub, cite
  commit and date).

Novelty check (23.10.): no work found that uses pairwise information-flow statistics conditioned on agents' private
inputs to identify a colluding pair of LLM agents and to separate two-way collusion from one-way leakage. Claim it as
"to our knowledge"; re-check arXiv once more before submission.
