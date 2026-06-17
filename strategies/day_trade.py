import logging
import pytz
from datetime import datetime
from .base import BaseStrategy
from data_feed import get_data
from indicators import (
    calculate_vwap, find_swings, detect_market_structure,
    is_rejection_candle,
)

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")


class DayTradeStrategy(BaseStrategy):
    """Structure + VWAP Reclaim — Claude Day Trade."""

    name = "Structure + VWAP Reclaim (Day Trade)"
    portfolio_key = "my_day_trade"
    default_rr = 2.0
    max_daily_trades = 3

    def check_signal(self, portfolio: dict, trades: dict) -> dict | None:
        now = datetime.now(ET)

        # Only run during NY session
        if not (9 <= now.hour < 16):
            return None
        # No trades in the first 5 min of the open
        if now.hour == 9 and now.minute < 35:
            return None
        # Max 3 trades per day
        if self.today_trade_count(trades, self.portfolio_key) >= self.max_daily_trades:
            return None
        # One open trade at a time
        if self.already_in_trade(trades, self.portfolio_key):
            return None

        df_15m = get_data("15m", 3)
        df_5m = get_data("5m", 2)

        if df_15m.empty or len(df_15m) < 10:
            return None
        if df_5m.empty or len(df_5m) < 10:
            return None

        # VWAP on 5m
        df_5m_v = calculate_vwap(df_5m)
        current = float(df_5m["Close"].iloc[-1])
        prev = float(df_5m["Close"].iloc[-2])
        vwap = float(df_5m_v["VWAP"].iloc[-1])

        # 15m structure
        sh_15, sl_15 = find_swings(df_15m, lookback=3)
        structure = detect_market_structure(sh_15, sl_15)
        if structure is None:
            return None

        direction = "long" if structure == "bullish" else "short"

        # VWAP reclaim: price crossed VWAP on the last candle
        if direction == "long":
            vwap_reclaim = prev < vwap <= current
        else:
            vwap_reclaim = prev > vwap >= current

        # Also allow near-VWAP (within 0.1%) as a softer entry
        near_vwap = abs(current - vwap) / vwap < 0.001

        if not vwap_reclaim and not near_vwap:
            return None

        # 5m rejection candle
        bias_map = {"bullish": "bullish", "bearish": "bearish"}
        rejection = (
            is_rejection_candle(df_5m, idx=-1, bias=structure)
            or is_rejection_candle(df_5m, idx=-2, bias=structure)
        )

        if not rejection and not vwap_reclaim:
            return None

        # SL: tightest 5m swing on the opposite side of the trade
        sh_5, sl_5 = find_swings(df_5m, lookback=3)
        if direction == "long":
            candidates = [s["price"] for s in sl_5 if s["price"] < current]
            sl = max(candidates) if candidates else current - current * 0.002
        else:
            candidates = [s["price"] for s in sh_5 if s["price"] > current]
            sl = min(candidates) if candidates else current + current * 0.002

        if abs(current - sl) < 2:
            return None  # SL too tight — likely noise

        return {
            "direction": direction,
            "entry": round(current, 2),
            "sl": round(sl, 2),
            "reasoning": (
                f"15m structure={structure} | VWAP={vwap:.2f} | "
                f"{'VWAP reclaim' if vwap_reclaim else 'near VWAP'} | "
                f"rejection={rejection}"
            ),
        }
