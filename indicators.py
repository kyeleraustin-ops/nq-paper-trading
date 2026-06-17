import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta

ET = pytz.timezone("America/New_York")


# ── VWAP ─────────────────────────────────────────────────────────────────────

def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Daily-reset VWAP with ±1 and ±2 standard-deviation bands."""
    df = df.copy()
    df["_date"] = df.index.date
    df["_tp"] = (df["High"] + df["Low"] + df["Close"]) / 3
    df["_tp_vol"] = df["_tp"] * df["Volume"]
    df["_sq_vol"] = (df["_tp"] ** 2) * df["Volume"]

    g = df.groupby("_date")
    df["_cum_tp_vol"] = g["_tp_vol"].cumsum()
    df["_cum_vol"] = g["Volume"].cumsum()
    df["_cum_sq"] = g["_sq_vol"].cumsum()

    df["VWAP"] = df["_cum_tp_vol"] / df["_cum_vol"]
    variance = (df["_cum_sq"] / df["_cum_vol"]) - df["VWAP"] ** 2
    df["_std"] = np.sqrt(variance.clip(0))
    df["VWAP_upper1"] = df["VWAP"] + df["_std"]
    df["VWAP_lower1"] = df["VWAP"] - df["_std"]
    df["VWAP_upper2"] = df["VWAP"] + 2 * df["_std"]
    df["VWAP_lower2"] = df["VWAP"] - 2 * df["_std"]

    return df.drop(columns=["_date", "_tp", "_tp_vol", "_sq_vol",
                             "_cum_tp_vol", "_cum_vol", "_cum_sq", "_std"])


# ── Swing highs / lows ────────────────────────────────────────────────────────

def find_swings(df: pd.DataFrame, lookback: int = 3) -> tuple[list, list]:
    """Return lists of swing-high and swing-low dicts with price/time/idx."""
    swing_highs, swing_lows = [], []
    n = len(df)

    for i in range(lookback, n - lookback):
        window = slice(i - lookback, i + lookback + 1)
        if df["High"].iloc[i] == df["High"].iloc[window].max():
            swing_highs.append({"price": float(df["High"].iloc[i]),
                                 "time": df.index[i], "idx": i})
        if df["Low"].iloc[i] == df["Low"].iloc[window].min():
            swing_lows.append({"price": float(df["Low"].iloc[i]),
                                "time": df.index[i], "idx": i})

    return swing_highs, swing_lows


# ── Market structure ──────────────────────────────────────────────────────────

def detect_market_structure(swing_highs: list, swing_lows: list) -> str | None:
    """Return 'bullish' (HH/HL), 'bearish' (LH/LL), or None."""
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None

    highs = [s["price"] for s in swing_highs[-3:]]
    lows = [s["price"] for s in swing_lows[-3:]]

    hh = all(highs[i] > highs[i - 1] for i in range(1, len(highs)))
    hl = all(lows[i] > lows[i - 1] for i in range(1, len(lows)))
    lh = all(highs[i] < highs[i - 1] for i in range(1, len(highs)))
    ll = all(lows[i] < lows[i - 1] for i in range(1, len(lows)))

    if hh and hl:
        return "bullish"
    if lh and ll:
        return "bearish"
    if hl:
        return "bullish"
    if lh:
        return "bearish"
    return None


def detect_bos(df: pd.DataFrame, swing_highs: list, swing_lows: list) -> str | None:
    """Detect most recent Break of Structure from the current close."""
    if df.empty:
        return None
    last = float(df["Close"].iloc[-1])

    if swing_highs and last > swing_highs[-1]["price"]:
        return "bullish"
    if swing_lows and last < swing_lows[-1]["price"]:
        return "bearish"
    return None


# ── Fair Value Gaps ───────────────────────────────────────────────────────────

def find_fvg(df: pd.DataFrame, fill_tolerance: float = 0.1) -> list:
    """Return a list of unfilled FVG dicts."""
    fvgs = []
    if len(df) < 3:
        return fvgs

    for i in range(2, len(df)):
        ph = float(df["High"].iloc[i - 2])
        pl = float(df["Low"].iloc[i - 2])
        ch = float(df["High"].iloc[i])
        cl = float(df["Low"].iloc[i])

        # Bullish FVG
        if ph < cl:
            gap_size = cl - ph
            sub_lows = df["Low"].iloc[i:]
            if float(sub_lows.min()) > ph + gap_size * fill_tolerance:
                fvgs.append({"type": "bullish", "top": cl, "bottom": ph,
                             "mid": (cl + ph) / 2, "size": gap_size,
                             "time": df.index[i - 1]})

        # Bearish FVG
        elif pl > ch:
            gap_size = pl - ch
            sub_highs = df["High"].iloc[i:]
            if float(sub_highs.max()) < pl - gap_size * fill_tolerance:
                fvgs.append({"type": "bearish", "top": pl, "bottom": ch,
                             "mid": (pl + ch) / 2, "size": gap_size,
                             "time": df.index[i - 1]})

    return fvgs


def price_in_fvg(price: float, fvgs: list, bias: str) -> dict | None:
    """Return the FVG dict if price is inside one aligned with bias, else None."""
    aligned = "bullish" if bias == "bullish" else "bearish"
    for fvg in reversed(fvgs):
        if fvg["type"] == aligned and fvg["bottom"] <= price <= fvg["top"]:
            return fvg
    return None


# ── Fibonacci ─────────────────────────────────────────────────────────────────

def fibonacci_levels(swing_high: float, swing_low: float, bias: str) -> dict:
    diff = swing_high - swing_low
    if bias == "bullish":
        base = swing_high
        sign = -1
    else:
        base = swing_low
        sign = 1

    return {lvl: base + sign * float(lvl) * diff
            for lvl in (0.236, 0.382, 0.500, 0.618, 0.705, 0.786)}


def price_at_fib(price: float, fib_levels: dict, tol_pct: float = 0.002) -> tuple:
    """Return (key, price) of the nearest key fib level within tolerance, or (None, None)."""
    for lvl in (0.500, 0.618, 0.705, 0.786):
        fp = fib_levels.get(lvl)
        if fp and abs(price - fp) / price <= tol_pct:
            return lvl, fp
    return None, None


# ── Session levels ────────────────────────────────────────────────────────────

def get_session_levels(df_5m: pd.DataFrame) -> dict:
    """Return Asia / London / NY session H/L and True Day Open for today."""
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    today = now.date()
    yesterday = today - timedelta(days=1)

    df = df_5m.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(et)
    else:
        df.index = df.index.tz_convert(et)

    def _hl(start_dt, end_dt):
        mask = (df.index >= start_dt) & (df.index < end_dt)
        sub = df[mask]
        if sub.empty:
            return None
        return {"high": float(sub["High"].max()), "low": float(sub["Low"].min())}

    def _dt(date, hhmm):
        return et.localize(datetime.combine(date, datetime.strptime(hhmm, "%H:%M").time()))

    sessions = {}
    sessions["asia"] = _hl(_dt(yesterday, "18:00"), _dt(today, "02:00"))
    sessions["london"] = _hl(_dt(today, "02:00"), _dt(today, "08:00"))
    sessions["ny"] = _hl(_dt(today, "09:30"), _dt(today, "16:00"))

    tdo_data = df[df.index >= _dt(today, "00:00")]
    if not tdo_data.empty:
        sessions["tdo"] = float(tdo_data["Open"].iloc[0])

    return {k: v for k, v in sessions.items() if v is not None}


# ── Rejection candle ──────────────────────────────────────────────────────────

def is_rejection_candle(df: pd.DataFrame, idx: int = -1, bias: str = None) -> bool:
    """True if the candle at idx is a pin-bar / wick-rejection aligned with bias."""
    c = df.iloc[idx]
    body = abs(float(c["Close"]) - float(c["Open"]))
    total = float(c["High"]) - float(c["Low"])
    if total == 0:
        return False

    upper_wick = float(c["High"]) - max(float(c["Close"]), float(c["Open"]))
    lower_wick = min(float(c["Close"]), float(c["Open"])) - float(c["Low"])

    if bias == "bearish":
        return upper_wick > total * 0.5 and body / total < 0.4
    if bias == "bullish":
        return lower_wick > total * 0.5 and body / total < 0.4
    return (upper_wick > total * 0.5 or lower_wick > total * 0.5) and body / total < 0.4


# ── Volume absorption ─────────────────────────────────────────────────────────

def detect_absorption(df: pd.DataFrame, idx: int = -1) -> bool:
    """High volume + small body = buyers/sellers absorbed."""
    if len(df) < 10:
        return False
    c = df.iloc[idx]
    avg_vol = float(df["Volume"].iloc[-10:].mean())
    avg_range = float((df["High"].iloc[-10:] - df["Low"].iloc[-10:]).mean())
    body = abs(float(c["Close"]) - float(c["Open"]))
    return float(c["Volume"]) > avg_vol * 1.5 and body < avg_range * 0.35


# ── Order blocks ──────────────────────────────────────────────────────────────

def find_order_blocks(df: pd.DataFrame, lookback: int = 20) -> list:
    """Last bearish candle before a bullish impulse (bullish OB) and vice-versa."""
    obs = []
    avg_range = float((df["High"].iloc[-lookback:] - df["Low"].iloc[-lookback:]).mean())

    for i in range(1, min(lookback, len(df) - 1)):
        prev = df.iloc[-(i + 1)]
        nxt = df.iloc[-i]

        # Bullish OB: bearish candle followed by strong bullish move
        if float(prev["Close"]) < float(prev["Open"]) and float(nxt["Close"]) > float(nxt["Open"]):
            if float(nxt["Close"]) - float(prev["Open"]) > avg_range * 0.5:
                obs.append({"type": "bullish", "top": float(prev["Open"]),
                            "bottom": float(prev["Low"]), "time": df.index[-(i + 1)]})

        # Bearish OB: bullish candle followed by strong bearish move
        elif float(prev["Close"]) > float(prev["Open"]) and float(nxt["Close"]) < float(nxt["Open"]):
            if float(prev["Open"]) - float(nxt["Close"]) > avg_range * 0.5:
                obs.append({"type": "bearish", "top": float(prev["High"]),
                            "bottom": float(prev["Open"]), "time": df.index[-(i + 1)]})

    return obs


# ── Utility ───────────────────────────────────────────────────────────────────

def price_near_level(price: float, level: float, tol_pct: float = 0.002) -> bool:
    if level == 0:
        return False
    return abs(price - level) / price <= tol_pct
