import logging
import pytz
from datetime import datetime
from .base import BaseStrategy
from data_feed import get_data, get_4h_data
from indicators import (
    find_swings, detect_bos, is_rejection_candle, price_near_level,
)
from trade_manager import create_trade

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")
CONTRACT_MULTIPLIER = 20


class SwingStrategy(BaseStrategy):
    """Weekly Level Fades — Claude Swing."""

    name = "Weekly Level Fades (Swing)"
    portfolio_key = "swing"
    default_rr = 2.0

    def open_trade(self, signal: dict, portfolio: dict, trades: dict) -> dict:
        entry = signal["entry"]
        sl = signal["sl"]
        direction = signal["direction"]
        risk = abs(entry - sl)
        tp = entry + risk * self.default_rr if direction == "long" else entry - risk * self.default_rr

        # Size to 1% account risk
        balance = portfolio["strategies"].get(self.portfolio_key, {}).get("balance", 50000)
        risk_dollars = balance * 0.01
        contracts = max(1, int(risk_dollars / (risk * CONTRACT_MULTIPLIER)))

        return create_trade(
            strategy_key=self.portfolio_key,
            direction=direction,
            entry=entry,
            sl=sl,
            tp=round(tp, 2),
            contracts=contracts,
            reasoning=signal.get("reasoning", ""),
        )

    def check_signal(self, portfolio: dict, trades: dict) -> dict | None:
        if self.already_in_trade(trades, self.portfolio_key):
            return None

        df_daily = get_data("1d", 90)
        df_weekly = get_data("1wk", 104)
        df_4h = get_4h_data()

        if df_daily.empty or len(df_daily) < 10:
            return None
        if df_weekly.empty or len(df_weekly) < 4:
            return None

        current = float(df_daily["Close"].iloc[-1])

        # Daily BOS for directional bias
        sh_d, sl_d = find_swings(df_daily, lookback=5)
        daily_bos = detect_bos(df_daily, sh_d, sl_d)
        if daily_bos is None:
            return None

        # Key levels: prior-week H/L + monthly open
        prev_wk_high = float(df_weekly["High"].iloc[-2])
        prev_wk_low = float(df_weekly["Low"].iloc[-2])

        now = datetime.now(ET)
        this_month = df_daily[df_daily.index.month == now.month]
        monthly_open = float(this_month["Open"].iloc[0]) if not this_month.empty else None

        key_levels = [("prev_wk_high", prev_wk_high), ("prev_wk_low", prev_wk_low)]
        if monthly_open:
            key_levels.append(("monthly_open", monthly_open))

        hit_name, hit_level = None, None
        for name, level in key_levels:
            if price_near_level(current, level, tol_pct=0.003):
                hit_name, hit_level = name, level
                break

        if hit_level is None:
            return None

        # Fade the level in the direction of daily bias
        if daily_bos == "bullish" and current >= hit_level * 0.998:
            direction = "short"  # price at resistance, fade with bullish HTF caution
        elif daily_bos == "bearish" and current <= hit_level * 1.002:
            direction = "long"   # price at support, fade with bearish HTF caution
        else:
            return None

        # Daily rejection candle required
        candle_bias = "bearish" if direction == "short" else "bullish"
        if not is_rejection_candle(df_daily, idx=-1, bias=candle_bias):
            return None

        # 4H BOS confirmation (optional but must not contradict)
        if not df_4h.empty and len(df_4h) >= 6:
            sh_4h, sl_4h = find_swings(df_4h, lookback=3)
            bos_4h = detect_bos(df_4h, sh_4h, sl_4h)
            expected_4h = "bullish" if direction == "long" else "bearish"
            if bos_4h and bos_4h != expected_4h:
                return None  # 4H contradicts

        # SL: structural level + 0.1% buffer
        buf = current * 0.001
        if direction == "short":
            highs = [s["price"] for s in sh_d[-3:] if s["price"] > current]
            sl = (min(highs) if highs else hit_level) + buf
        else:
            lows = [s["price"] for s in sl_d[-3:] if s["price"] < current]
            sl = (max(lows) if lows else hit_level) - buf

        if abs(current - sl) < 5:
            return None  # too tight for a swing trade

        return {
            "direction": direction,
            "entry": round(current, 2),
            "sl": round(sl, 2),
            "reasoning": (
                f"Daily BOS={daily_bos} | Level={hit_name} @ {hit_level:.2f} | "
                f"Daily rejection candle | direction={direction}"
            ),
        }
