import logging
import pytz
from .base import BaseStrategy
from data_feed import get_data, get_4h_data
from indicators import (
    calculate_vwap, find_swings, detect_bos,
    find_fvg, price_in_fvg, is_rejection_candle, detect_absorption,
)

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")


class Strat2(BaseStrategy):
    """FVG + VWAP Absorption (User S2)."""

    name = "FVG + VWAP Absorption (S2)"
    portfolio_key = "strat2"
    default_rr = 2.0

    def check_signal(self, portfolio: dict, trades: dict) -> dict | None:
        if self.already_in_trade(trades, self.portfolio_key):
            return None

        df_5m = get_data("5m", 3)
        df_15m = get_data("15m", 5)
        df_1h = get_data("1h", 10)
        df_4h = get_4h_data()
        df_1d = get_data("1d", 60)

        if df_5m.empty or len(df_5m) < 10:
            return None
        if df_15m.empty or len(df_15m) < 10:
            return None
        if df_1d.empty:
            return None

        current = float(df_5m["Close"].iloc[-1])
        prev = float(df_5m["Close"].iloc[-2])

        # ── HTF Bias ─────────────────────────────────────────────────────────
        sh_1d, sl_1d = find_swings(df_1d, lookback=5)
        htf_bias = detect_bos(df_1d, sh_1d, sl_1d)

        if htf_bias is None and not df_4h.empty and len(df_4h) >= 6:
            sh_4h, sl_4h = find_swings(df_4h, lookback=3)
            htf_bias = detect_bos(df_4h, sh_4h, sl_4h)

        if htf_bias is None:
            return None

        direction = "long" if htf_bias == "bullish" else "short"

        # ── VWAP ──────────────────────────────────────────────────────────────
        df_5m_v = calculate_vwap(df_5m)
        vwap = float(df_5m_v["VWAP"].iloc[-1])

        # Candle closes into VWAP (price approaches from either side)
        if direction == "long":
            closes_into_vwap = prev < vwap and current >= vwap * 0.9995
        else:
            closes_into_vwap = prev > vwap and current <= vwap * 1.0005

        if not closes_into_vwap:
            return None

        # ── FVG ───────────────────────────────────────────────────────────────
        fvgs = find_fvg(df_15m) + find_fvg(df_5m)
        if not df_1h.empty:
            fvgs += find_fvg(df_1h)
        in_fvg = price_in_fvg(current, fvgs, htf_bias)

        if not in_fvg:
            return None

        # ── Absorption (high-vol, small-body candle) ──────────────────────────
        absorption = detect_absorption(df_5m, idx=-2) or detect_absorption(df_5m, idx=-3)

        # ── Rejection / trigger candle ────────────────────────────────────────
        rejection = (is_rejection_candle(df_5m, idx=-1, bias=htf_bias) or
                     is_rejection_candle(df_5m, idx=-2, bias=htf_bias))

        if not rejection and not absorption:
            return None

        # ── SL ────────────────────────────────────────────────────────────────
        sh_15, sl_15 = find_swings(df_15m, lookback=3)
        if direction == "long":
            lows = [s["price"] for s in sl_15 if s["price"] < current]
            sl = max(lows) if lows else current - current * 0.003
        else:
            highs = [s["price"] for s in sh_15 if s["price"] > current]
            sl = min(highs) if highs else current + current * 0.003

        if abs(current - sl) < 3:
            return None

        return {
            "direction": direction,
            "entry": round(current, 2),
            "sl": round(sl, 2),
            "reasoning": (
                f"HTF={htf_bias} | VWAP reclaim | FVG={in_fvg['type']} | "
                f"absorption={absorption} | rejection={rejection}"
            ),
        }
