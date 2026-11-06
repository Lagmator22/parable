# Model response benchmark

On 7 November 2026, Parable sent six fixed market scenarios to each configured model using real API calls. The scenarios covered a steady rise, steady fall, sharp dip, flat market, spike followed by a crash, and low cash. A valid answer was a parseable buy, sell or hold decision. The table shows the models that returned valid decisions in all six scenarios, plus the rule baseline.

| Model | Valid responses | Mean response time |
|---|---:|---:|
| Gemma 4 31B (Jev) | 6/6 | 1.5 s |
| DeepSeek V4.1 Flash (Jev) | 6/6 | 1.5 s |
| Gemini 3.1 Flash-Lite | 6/6 | 5.6 s |
| Gemini 3.5 Flash-Lite | 6/6 | 7.3 s |
| Simple rule | 6/6 | Under 0.1 s |

This small run measures response validity and latency. Profitability requires a separate test. The dashboard's model comparison includes stopped bots and shows average and worst vault returns. Its Practice Arena runs simulated market scenarios.

To repeat the response test with your configured providers, run from the repo root:

```bash
(cd engine && uv run python ../scripts/brain_benchmark.py)
```
