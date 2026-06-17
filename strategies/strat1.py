import logging
import pytz
from .base import BaseStrategy
from data_feed import get_data, get_4h_data
from indicators import (
    calculate_vwap, find_swings, detect_bos,
    find_fvg, price_in_fvg, fibonacci_levels, price_at_fib,
    is_rejection_candle, get_session_levels, price_near_level,
)

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")


class Strat1(BaseStrategy):
    """HTF Flow + Session Levels + Confluence (User S1)."""

    name = "HTF Flow + Session Levels + Confluence (S1)"
    portfolio_key = "strat1"
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
        if df_1d.empty or len(df_1d) < 10:
            return None

        current = float(df_5m["Close"].iloc[-1])

        # ── HTF Bias ─────────────────────────────────────────────────────────
        sh_1d, sl_1d = find_swings(df_1d, lookback=5)
        bos_1d = detect_bos(df_1d, sh_1d, sl_1d)

        bos_4h = None
        if not df_4h.empty and len(df_4h) >= 6:
            sh_4h, sl_4h = find_swings(df_4h, lookback=3)
            bos_4h = detect_bos(df_4h, sh_4h, sl_4h)

        htf_bias = bos_1d or bos_4h
        if htf_bias is None:
            return None

        direction = "long" if htf_bias == "bullish" else "short"

        # ── Session levels (DOL) ──────────────────────────────────────────────
        sessions = get_session_levels(df_5m)
        near_session = False
        for sdata in sessions.values():
            if isinstance(sdata, dict):
                if price_near_level(current, sdata.get("high", 0), 0.003) or \
                   price_near_level(current, sdata.get("low", 0), 0.003):
                    near_session = True
                    break

        # ── FVG (any TF above 5m, or 5m itself) ──────────────────────────────
        fvgs = find_fvg(df_15m)
        if not df_1h.empty:
            fvgs += find_fvg(df_1h)
        fvgs += find_fvg(df_5m)
        in_fvg = price_in_fvg(current, fvgs, htf_bias)

        # ── VWAP / SD bands ───────────────────────────────────────────────────
        df_5m_v = calculate_vwap(df_5m)
        vwap = float(df_5m_v["VWAP"].iloc[-1])
        upper1 = float(df_5m_v["VWAP_upper1"].iloc[-1])
        lower1 = float(df_5m_v["VWAP_lower1"].iloc[-1])

        near_vwap = (price_near_level(current, vwap, 0.002) or
                     price_near_level(current, upper1, 0.002) or
                     price_near_level(current, lower1, 0.002))

        # ── Fibonacci from 15m swing ──────────────────────────────────────────
        sh_15, sl_15 = find_swings(df_15m, lookback=3)
        at_fib = False
        fib_key = None
        if sh_15 and sl_15:
            rh = sh_15[-1]["price"]
            rl = sl_15[-1]["price"]
            fibs = fibonacci_levels(rh, rl, htf_bias)
            fib_key, _ = price_at_fib(current, fibs, tol_pct=0.002)
            at_fib = fib_key is not None

        # ── Confluence gate (need ≥ 2 of 3) ──────────────────────────────────
        confluence = sum([bool(in_fvg), near_vwap, at_fib])
        if confluence < 2:
            return None

        # ── Trigger: rejection candle ─────────────────────────────────────────
        rejection = (is_rejection_candle(df_5m, idx=-1, bias=htf_bias) or
                     is_rejection_candle(df_5m, idx=-2, bias=htf_bias))
        if not rejection:
            return None

        # ── SL: recent 15m swing on opposite side ─────────────────────────────
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
                f"HTF={htf_bias} | FVG={bool(in_fvg)} | VWAP={near_vwap} | "
                f"Fib={fib_key} | session={near_session} | "
                f"confluence={confluence}/3 | rejection=True"
            ),
        }
