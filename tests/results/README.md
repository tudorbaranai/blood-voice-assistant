# Bench results

Every saved run of the brain benches. Open any `.md` file for the full answers;
the `.json` files hold the same data for `python tests/blood_bench.py --compare`.
All runs: `qwen3:4b-instruct` on a GTX 1650 Ti (4 GB), 8 GB RAM.

## Brain bench: `blood_bench.py` (24 Oct 2026)

56 commands and questions, graded against a pretend house. "x2" or "x3" means
every case ran two or three times, to catch answers that change between runs.

| Run | Prompt | What changed | Passed | Lies | Avg answer |
|---|---|---|---|---|---|
| [v8](bench-v8-qwen3-4b-2026-10-24_22-03.md) | v8 | "the only way to change a device is a tool call"; lists allowed | 50/56 | 0 | 6.2 s |
| [v9](bench-v9-qwen3-4b-2026-10-24_22-09.md) | v9 | Home Assistant's real tool names; check live state before answering | 51/56 | 0 | 3.4 s |
| [v9, all on GPU](bench-v9-qwen3-4b-allGPU-2026-10-24_22-13.md) | v9 | every model layer on the GPU | 48/56 | 1 | 1.4 s |
| [v10 x2](bench-v10-allGPU-x2-2026-10-24_22-16.md) | v10 | "too dark" → lights on; rankings allowed; "(in N days)" in the calendar | 106/112 | 0* | 1.4 s |
| [v10 x2, temp 0.2](bench-v10-allGPU-temp0.2-x2-2026-10-24_22-19.md) | v10 | temperature 0.2 instead of the default | 106/112 | 0* | 1.3 s |
| [v11 x3](bench-v11-devices-allGPU-x3-2026-10-24_22-22.md) | v11 | hint rules spelled out as tool calls; "never promise without the call" (device cases only) | 78/90 | 10 | 1.7 s |
| [v12 x2](bench-v12-allGPU-x2-2026-10-24_22-26.md) | v12 | one worked example for "it's too dark in here" | 105/112 | 3 | 1.4 s |
| [v12 x3, hints only](bench-v12-implicit-x3-2026-10-24_22-25.md) | v12 | only the hint and multi-device cases | 16/21 | 5 | 1.4 s |
| [**v12, blood-brain**](bench-v12-blood-brain-2026-10-24_22-47.md) | v12 | the final [Modelfile](../../tools/blood-brain.Modelfile) settings | **52/56** | 3 | **1.4 s** |

\* The lie detector got stricter during the session: from v11 on it also flags
promises like "I'll turn on the lights" when nothing was switched. The v10 runs
gave exactly those answers to the hint cases, so with today's detector they would
show lies too.

What the table shows:
- **Speed came from the GPU, not the prompt.** Same prompt (v9), 3.4 s → 1.4 s.
- **Hints are the one category that never got solid.** Every prompt from v10 to
  v12 still fails some "it's too dark"-style cases.
- **Temperature 0.2 didn't change the score** (106/112 either way). blood-brain
  uses it anyway for steadier answers.

## Earlier benches

| File | Bench | What it tested |
|---|---|---|
| [results-2026-10-09_18-11](results-2026-10-09_18-11.md) | `test-models.ps1` | the first test: `qwen3:1.7b` vs `qwen3:4b-instruct`, default temperature vs 0.2, prompt v2 |
| [brains-2026-10-12_19-24](brains-2026-10-12_19-24.md) | `compare-brains.ps1` | three models on the trick questions with prompt v5: 1.7b invents a scientist, the thinking model takes up to 4 minutes per answer |
| [brains-2026-10-12_19-45](brains-2026-10-12_19-45.md) | `compare-brains.ps1` | prompt v6, first draft: still guesses what weekday Christmas is |
| [brains-2026-10-12_19-46](brains-2026-10-12_19-46.md) | `compare-brains.ps1` | prompt v6, final: says it can only see four weeks ahead |

Speech-to-text results are in [`../stt/results/`](../stt/results/).
