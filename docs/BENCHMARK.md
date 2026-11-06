# Brain benchmark (run Sat 7 Nov 2026, 00:25 IST)

Every brain answered the same 6 market situations (steady rise, steady fall, sharp dip, flat, spike then crash, low cash).
Real API calls; script: `cd engine && uv run python ../spikes/brain_benchmark.py`. A "valid" answer is a well-formed
buy/sell/hold decision; anything else (error, rate limit, garbage) would make the bot fall back to the simple rule.

| Brain | Valid | Avg time | Notes |
|---|---|---|---|
| Jev · Gemma 4 31B (Autoloops) | 6/6 | 1.5 s | Returns probabilities; trade size follows confidence |
| Jev · DeepSeek V4.1 Flash (Autoloops) | 6/6 | 1.5 s | Cautious: holds in 4 of 6 situations |
| Gemini 3.5 Flash-Lite | 6/6 | 7.3 s | |
| Gemini 3.1 Flash-Lite | 6/6 | 5.6 s | |
| Simple rule (no AI) | 6/6 | 0 s | Baseline |
| Gemini 3.6 / 3.5 / 3 Flash Preview / 2.5 Flash | 0–2/6 | — | Free-tier rate limits (HTTP 429) |
| Gemma 4 31B / 26B via Google API | 1–2/6 | 14–18 s | Google HTTP 500s and timeouts |
| Claude Haiku / Sonnet / Opus 5.5 | 0/6 | — | Account has no credit; hidden on the site |

The live demo uses only the brains that answered 6/6.
