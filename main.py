"""GTA VI launch-day Twitch forecast (make.fun gta6-twitch-ccu-forecast-01).

Pure stdlib Python 3.13. Reads every <id>.in in the input dir, writes <id>.out
per case: {"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}]} for h = 2..24.

Method — launch-shape neighbours:
  A launch day's hourly curve is mostly its *shape* (when each timezone
  unlocks and wakes up), not its size. So each comparable launch contributes
  its release-day curve as log-ratios lr_h = ln(viewers_h / viewers_hour1).
  Comparables are weighted by how close their hour-1 print is to this case's
  hour-1 print (Gaussian kernel on ln h1, bandwidth 0.9): a huge hour 1 means
  the launch already unlocked across NZ/Asia/Europe, so its neighbours are the
  big rolling-midnight launches (flat-to-rising curves, peak ~1-2.7x hour 1);
  a tiny hour 1 means a simultaneous global unlock is still ahead, so its
  neighbours are the small-hour-1 launches (steep ramps, 10-1000x).
  For each hour, the forecast quantiles are the weighted percentiles of the
  neighbours' log-ratios, with a minimum spread that widens over the day
  (honest uncertainty: the 5-95 band must stay wide enough to cover).
  Median is shrunk 10% toward persistence (lr = 0) as a hedge.

  Why this beats the house baseline (flat at hour 1, loss ~0.387 on
  practice): the baseline ignores the known diurnal shape — every big
  rolling launch dips to ~0.5-0.7x in hours 2-6 (overnight UTC, US not yet
  unlocked) and rises to ~1.0-2.6x by hours 16-21 (US daytime/evening).
  The neighbours' median captures that shape; the baseline's median does not.

Validation (validate.py, leave-one-out over the 38 comparables in the kit):
  mean pinball loss vs house baseline — see README/validation output.
  Deterministic: sorted input order, fixed arithmetic, no randomness, no I/O
  besides the case files. Runs in well under 1s per case.
"""

import datetime
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
# Gaussian kernel bandwidth on ln(hour-1 viewers) for neighbour weighting.
# Picked by leave-one-out grid search (tune.py): 1.2 balances the big-launch
# class (the final's class) with the small-hour-1 class; 0.9-1.2 are all close.
BANDWIDTH = 1.2
# Median shrinkage toward persistence (0 = full shape, 1 = flat baseline).
SHRINK = 0.15
# Minimum half-spread of the 5-95 band in log units, growing with hour:
# even the best shape guess stays uncertain, wider later in the day.
MIN_SPREAD = 0.35          # log units at hour 2
SPREAD_GROWTH = 0.03       # extra log units per hour after hour 2


def round2(x):
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def release_day_ratios(comparable):
    """Return {hour: viewers} for the comparable's UTC release day (hours 1-24)."""
    try:
        ds = comparable["day_start"]
        y, mo, d = int(ds[0:4]), int(ds[5:7]), int(ds[8:10])
    except Exception:
        return {}
    out = {}
    for p in comparable.get("hourly") or []:
        try:
            frm = p["from"]
            t = datetime.datetime(int(frm[0:4]), int(frm[5:7]), int(frm[8:10]),
                                  int(frm[11:13]), tzinfo=datetime.timezone.utc)
            d0 = datetime.datetime(y, mo, d, tzinfo=datetime.timezone.utc)
            h = int((t - d0).total_seconds() // 3600) + 1
            v = p.get("viewers")
            if 1 <= h <= 24 and v is not None and v > 0:
                out[h] = v
        except Exception:
            continue
    return out


def weighted_quantile(pairs, tau):
    """Weighted percentile of [(value, weight)] at tau in (0, 1)."""
    pts = sorted((v, w) for v, w in pairs if w > 0)
    total = sum(w for _, w in pts)
    if total <= 0 or not pts:
        return None
    target = tau * total
    acc = 0.0
    for i, (v, w) in enumerate(pts):
        acc += w
        if acc >= target:
            if i + 1 < len(pts) and acc - w < target:
                # Interpolate toward the next point for smoothness.
                nxt = pts[i + 1][0]
                frac = (target - (acc - w)) / w if w > 0 else 0.0
                return v + frac * (nxt - v)
            return v
    return pts[-1][0]


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    log_p1 = math.log(p1)

    # Neighbour log-ratio curves from the comparables.
    neighbours = []  # (weight, {hour: log-ratio})
    for comp in case.get("comparables") or []:
        curve = release_day_ratios(comp)
        h1 = curve.get(1)
        if not h1 or h1 <= 0 or len(curve) < 12:
            continue
        w = math.exp(-((math.log(h1) - log_p1) / BANDWIDTH) ** 2)
        if w < 0.02:
            continue
        lr = {h: math.log(v / h1) for h, v in curve.items()}
        neighbours.append((w, lr))

    hours = []
    for row in case["forecast"]:
        h = int(row["hour"])
        pairs = [(lr[h], w) for w, lr in neighbours if h in lr]
        if pairs and sum(w for _, w in pairs) > 0.5:
            med = weighted_quantile(pairs, 0.5)
            q05 = weighted_quantile(pairs, 0.05)
            q25 = weighted_quantile(pairs, 0.25)
            q75 = weighted_quantile(pairs, 0.75)
            q95 = weighted_quantile(pairs, 0.95)
            med = (1.0 - SHRINK) * med
            spread = max(q95 - q05, 2.0 * (MIN_SPREAD + SPREAD_GROWTH * (h - 2)))
            # Re-centre the band on the shrunk median with at least the min spread.
            lo = min(q05, med - spread / 2.0)
            hi = max(q95, med + spread / 2.0)
            q25 = min(max(q25, lo), med)
            q75 = max(min(q75, hi), med)
            qs = [lo, q25, med, q75, hi]
        else:
            # Fallback: house baseline shape (flat + widening spread).
            qs = [math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z]
            qs = [math.log(q) for q in qs]
        out_q = []
        prev = None
        for q in qs:
            val = round2(p1 * math.exp(max(-9.0, min(9.0, q))))
            val = max(val, 1)
            if prev is not None and val < prev:
                val = prev
            out_q.append(val)
            prev = val
        hours.append({"hour": h, "q": out_q})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
