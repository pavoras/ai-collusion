# Resources

## Sprint

- Sprint page (tabs Overview, Resources, Guidelines, Schedule; submission form):
  https://apartresearch.com/sprints/ai-collusion-research-sprint-2026-10-23-to-2026-10-25
- Report template (makes a Google Docs copy):
  https://docs.google.com/document/d/1Y5wd3VRbXU5N08BvAGiJUQTaWbMCSPjhzXsR-ozuehg/copy?usp=sharing
  Use the template from the Guidelines tab, not an older one from an acceptance e-mail.
- Sprint Discord: https://discord.gg/XswWBvugYs (channels announcements, team-forming, help-desk with @Support)
- Apart Discord: https://discord.gg/dYUWDm7Ben
- Contact: sprints@apartresearch.com
- Deadline: Sunday 25.10. 23:59 AoE = **Monday 26.10. 12:59 German time**
- A German briefing with schedule, all 12 questions, rules and judging is kept locally (not in the repo).

## Question 1.4

- Core paper: Bonjour, Aggarwal, Bhargava (2022), "Information-Theoretic Approach to Detect Collusion in
  Multi-Agent Games", UAI 2022, PMLR 180:223–232. https://proceedings.mlr.press/v180/bonjour22a.html
  (PDF: https://proceedings.mlr.press/v180/bonjour22a/bonjour22a.pdf). No author code. Notes: `METHOD.md`.
- Apart's suggested weekend project: (1) implement net influence, test on scripted iterated RPS with one known pair;
  (2) four-agent discrete game with exactly one seeded pair; (3) compare net influence, plain action correlation
  and an LLM judge at ranking the true pair; (4) optional: apply to the Agrawal double auction as a quantitative
  "plus factor". Risk low to medium, harness a few hundred lines, scripted part $0, LLM pilot 20–40 games of
  15–25 rounds for about $5–50, 16 GB laptop, no GPU.
- Starter code for 1.4 (auction environment):
  https://github.com/poseidon-research/collusion_hackathon/tree/main/llm-agent-collusion
  - Setup: `uv sync` in `llm-agent-collusion/` (or `./setup.sh llm-agent-collusion` from repo root). Keys in
    repo-root `compute.env` (copy `compute.env.example`): `OPENROUTER_API_KEY`, or `NEBIUS_API_KEY` with an open
    model such as `--seller_models qwen/qwen3-14b`. Do not set `LLM_MODEL`.
  - Smoke test (~30 calls): `uv run python src/continuous_double_auction/simulation.py --rounds 5 --tag smoke`
    (add `--buyer_models zip` for ~15 calls). Positive control (90 calls): `... --seller_comms_enabled --tag comms`.
  - Options: `--sellers/--buyers` (3/3), `--rounds` (15), `--seeds`, `--seller_models`, `--temperature` (0.7),
    `--seller_comms_enabled`, `--oversight_enabled`, `--llm_eval`, `--log_dir`, `--tag`. Prints a cost estimate first.
  - Output: `results/<run>/collusion_metrics.json` (collusion index 0 = competitive, 1 = cartel).
  - Upstream: https://github.com/andyjliu/llm-agent-collusion, paper Agrawal et al.: https://arxiv.org/abs/2507.01413
- Related: model-internals collusion detector (Rose et al. 2026): https://arxiv.org/abs/2604.01151

## Models and APIs

- Nebius AI Studio (default route of the starter repo): https://studio.nebius.com/
- OpenRouter: https://openrouter.ai/
- Price pages: OpenAI https://developers.openai.com/api/docs/pricing ·
  Google https://ai.google.dev/gemini-api/docs/pricing · Mistral https://docs.mistral.ai/inference/pricing
- Modal (GPU cloud, $50 credit per participant): https://modal.com/
- Set a spending limit at the provider (about $30).

## Other environments and papers (from the sprint Resources tab)

- Starter repo, all questions: https://github.com/poseidon-research/collusion_hackathon
- Colosseum: https://github.com/umass-ai-safety/colosseum (paper https://arxiv.org/abs/2602.15198)
- LLMCartel: https://github.com/mattriemer/LLMCartel
- Algorithmic pricing (Fish-style duopoly): https://github.com/luciasauer/algorithmic_pricing_llms
- focal-points: https://github.com/EmanueleLM/focal-points
- LLM-Trust-Breaking: https://github.com/Jerick-1380/LLM-Trust-Breaking
- TraceGuard: https://github.com/linhkid/TraceGuard
- ColludeBench: https://github.com/Ostailor/Steganographic_Collusion
- collusive-llm-agents: https://github.com/smojha/collusive-llm-agents
- Voluntary Collusion (Liar's Bar, Cleanup): https://github.com/AgentSafety2025/LLM-Agent-collusion
- Dolos-1.5B (red-teaming model): https://huggingface.co/Poseidon-Research/Dolos-1.5B
- Papers: Fish et al. 2024 https://arxiv.org/abs/2404.00806 · Shi et al. 2026 https://arxiv.org/abs/2607.05132 ·
  Keppo et al. 2026 https://arxiv.org/abs/2603.20281
