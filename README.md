# BMR-Com Biofuels desk

Soybean oil as the anchor, with the feedstocks it competes with (canola, palm, used cooking oil, tallow, distillers corn oil),
the credits a producer earns (D4/D5/D6/D3 RINs, California/Oregon/Washington clean-fuel credits, the 45Z tax credit) and the
policy that sets them (RFS volumes, small refinery exemptions, 45Z rules, trade measures).

The site shows outputs and the variables behind them. Code, raw downloads, run logs and model assumptions stay in the repo.

## Tabs
| Tab | What it shows |
|---|---|
| Overview | Soybean oil, ULSD, BOHO, RIN prices, LCFS, palm/canola/UCO; desk read; margins at screen prices; 2026 mandate check |
| Input / output | Per-gallon stack for each pathway (feedstock → BD/RD/SAF → ULSD + RINs + LCFS + 45Z + co-products − feedstock − opex), breakeven D4, 2026 vs 2027 rules |
| RINs & mandate | D4/D6/D3 futures, RVO vs EMTS generation, D4 by fuel, domestic vs imported RINs |
| Feedstocks | Cash fats and oils (USDA AMS), soy vs palm, EIA feedstock mix and soybean oil share, WASDE soybean oil |
| LCFS & 45Z | California, Oregon, Washington credit prices; credit value per gallon by pathway |
| Policy | RVO table, SRE decisions, dated policy timeline, Federal Register feed, watched agency pages |
| News | Price- and production-relevant headlines (Reuters, Bloomberg, WSJ) |
| Primers | One primer per variable and how the whole system fits together |

## Data and schedule
| Workflow | When | What |
|---|---|---|
| `daily` | weekdays 22:35 UTC | TradingView prices → economics + balance models; news; Federal Register + policy page watch |
| `weekly` | Saturday 14:00 UTC | USDA AMS cash fats/oils, CARB weekly LCFS, EIA spot ULSD/jet |
| `monthly` | days 16/19/22, 28, 2, 10/12 | EPA EMTS RIN generation; CARB/OR/WA credit reports; EIA feedstocks, capacity, MER; WASDE + PSD |
| `catch-up` | daily 02:43 UTC | reruns any feed that failed or is late (`pipelines/catchup.py`) |
| `pages` | after each data run, on pushes | builds `_site/` and publishes it |

Run state per source: `data/status/<source>.json`; history: `logs/<source>.jsonl`; catch-up results: `data/catchup.json` (none published).

## One-time setup (repo admin)
1. Settings → Pages → Source: **GitHub Actions**.
2. Settings → Actions → General → Workflow permissions: **Read and write**.
3. Actions → run `daily`, `weekly`, `monthly` (only = all) once to backfill.

## Layout
```
pipelines/   fetchers (prices, epa_emts, eia, lcfs, ams, wasde, psd, policy_watch, news), build_site, catchup
models/      economics.py (per-gallon margins, BOHO, breakeven D4), balance.py (RVO vs generation, feedstock mix)
data/manual/ RVO, SRE and policy timeline tables; assumptions.json (conversion factors, EVs, CI scores, opex)
primers/     primers.md (rendered to data/primers.json at build)
```
Manual tables are edited by hand when EPA, Treasury or CARB act; each row carries its source.
