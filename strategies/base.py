import pytz
from datetime import datetime
from trade_manager import create_trade

ET = pytz.timezone("America/New_York")


class BaseStrategy:
    name: str = "Base"
    portfolio_key: str = "base"
    default_rr: float = 2.0

    def check_signal(self, portfolio: dict, trades: dict) -> dict | None:
        raise NotImplementedError

    def open_trade(self, signal: dict, portfolio: dict, trades: dict) -> dict:
        entry = signal["entry"]
        sl = signal["sl"]
        direction = signal["direction"]
        risk = abs(entry - sl)

        if direction == "long":
            tp = entry + risk * self.default_rr
        else:
            tp = entry - risk * self.default_rr

        contracts = signal.get("contracts", 1)

        return create_trade(
            strategy_key=self.portfolio_key,
            direction=direction,
            entry=entry,
            sl=sl,
            tp=round(tp, 2),
            contracts=contracts,
            reasoning=signal.get("reasoning", ""),
        )

    def already_in_trade(self, trades: dict, strategy_key: str) -> bool:
        return any(
            t["strategy"] == strategy_key and t["status"] == "open"
            for t in trades.get("trades", [])
        )

    def today_trade_count(self, trades: dict, strategy_key: str) -> int:
        today = datetime.now(ET).date().isoformat()
        return sum(
            1 for t in trades.get("trades", [])
            if t["strategy"] == strategy_key and t["entry_time"][:10] == today
        )
