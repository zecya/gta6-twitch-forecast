# GTA VI Twitch CCU Forecast — make.fun entry

[![make.fun bounty](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/zecya/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/zecya/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

Forecasts Grand Theft Auto VI's launch-day Twitch concurrent viewers hour by hour (hours 2-24, five quantiles per hour) from everything known at the end of hour 1. The method is launch-shape neighbours: each past big launch contributes its hourly curve as a log-ratio to its own first hour, weighted by how close its first-hour size is to this case's; per-hour quantiles are weighted percentiles of those ratios, with the median shrunk 15% toward persistence and the 5-95% band forced to widen honestly as the day goes on. Pure Python 3.13 standard library, deterministic, no network, about 0.07s per case.

## Run

Put the case files (`*.in`) in a folder, set the input/output folders, and run:

```
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

It reads every `*.in` file in name order and writes one `.out` forecast per case.

Entry for the make.fun bounty "Forecast GTA VI's launch-day Twitch viewers hour by hour": https://make.fun/bounty/gta6-twitch-ccu-forecast-01

Optional: earn referral rewards, a second way to make money: https://make.fun/r/zehhbzz6
