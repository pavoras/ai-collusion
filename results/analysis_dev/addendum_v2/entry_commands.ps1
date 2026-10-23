# Offline command catalogue. Real additions require the amendment freeze commit first.
# Execute collection according to collection_v2.json execution_schedule.
# Judge commands use $Market, $Level, and $JudgeRun for each declared source/index/level.

# core.C1-NW; nominal calls: 24000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry core.C1-NW --run v2_core_C1-NW --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 48000
# lookalike.LX; nominal calls: 16000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry lookalike.LX --run v2_lookalike_LX --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 32000
# lookalike.LX-swap; nominal calls: 16000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry lookalike.LX-swap --run v2_lookalike_LX-swap --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 32000
# lookalike.LY; nominal calls: 16000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry lookalike.LY --run v2_lookalike_LY --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 32000
# lookalike.LY-swap; nominal calls: 16000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry lookalike.LY-swap --run v2_lookalike_LY-swap --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 32000
# lookalike.LZ; nominal calls: 16000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry lookalike.LZ --run v2_lookalike_LZ --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 32000
# lookalike.LZ-swap; nominal calls: 16000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry lookalike.LZ-swap --run v2_lookalike_LZ-swap --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 32000
# labs.gemma-12b.N0.A3; nominal calls: 8000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry labs.gemma-12b.N0.A3 --run v2_labs_gemma-12b_N0_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 16000
# labs.gemma-12b.C1.A3; nominal calls: 12000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry labs.gemma-12b.C1.A3 --run v2_labs_gemma-12b_C1_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 24000
# labs.ministral-8b.N0.A3; nominal calls: 8000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry labs.ministral-8b.N0.A3 --run v2_labs_ministral-8b_N0_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 16000
# labs.ministral-8b.C1.A3; nominal calls: 12000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry labs.ministral-8b.C1.A3 --run v2_labs_ministral-8b_C1_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 24000
# sizes.qwen-4b.N0.A3; nominal calls: 8000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry sizes.qwen-4b.N0.A3 --run v2_sizes_qwen-4b_N0_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 16000
# sizes.qwen-4b.C1.A3; nominal calls: 12000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry sizes.qwen-4b.C1.A3 --run v2_sizes_qwen-4b_C1_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 24000
# sizes.gemma-e4b.N0.A3; nominal calls: 8000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry sizes.gemma-e4b.N0.A3 --run v2_sizes_gemma-e4b_N0_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 16000
# sizes.gemma-e4b.C1.A3; nominal calls: 12000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry sizes.gemma-e4b.C1.A3 --run v2_sizes_gemma-e4b_C1_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 24000
# sizes.ministral-3b.N0.A3; nominal calls: 8000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry sizes.ministral-3b.N0.A3 --run v2_sizes_ministral-3b_N0_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 16000
# sizes.ministral-3b.C1.A3; nominal calls: 12000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry sizes.ministral-3b.C1.A3 --run v2_sizes_ministral-3b_C1_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 24000
# mixed.D.A3; nominal calls: 8000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry mixed.D.A3 --run v2_mixed_D_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 16000
# mixed.C1-XX.A3; nominal calls: 12000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry mixed.C1-XX.A3 --run v2_mixed_C1-XX_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 24000
# mixed.H-XYZZ.A3; nominal calls: 8000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry mixed.H-XYZZ.A3 --run v2_mixed_H-XYZZ_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 16000
# mixed.C1-XY.A3; nominal calls: 12000
.venv/Scripts/python experiments/run_llm.py --collection-manifest experiments/manifests/collection_v2.json --entry mixed.C1-XY.A3 --run v2_mixed_C1-XY_A3 --results results/analysis_dev/entry_dry_runs --dry-run --max-calls 24000
# judge.qwen9b.A1; nominal calls: 40
.venv/Scripts/python experiments/judge.py $Market --collection-manifest experiments/manifests/collection_v2.json --entry judge.qwen9b.A1 --run $JudgeRun --results results/analysis_dev/entry_dry_runs --model qwen-9b --level $Level --dry-run
# judge.qwen9b.A2; nominal calls: 240
.venv/Scripts/python experiments/judge.py $Market --collection-manifest experiments/manifests/collection_v2.json --entry judge.qwen9b.A2 --run $JudgeRun --results results/analysis_dev/entry_dry_runs --model qwen-9b --level $Level --dry-run
# judge.qwen9b.A3; nominal calls: 280
.venv/Scripts/python experiments/judge.py $Market --collection-manifest experiments/manifests/collection_v2.json --entry judge.qwen9b.A3 --run $JudgeRun --results results/analysis_dev/entry_dry_runs --model qwen-9b --level $Level --dry-run
