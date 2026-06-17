import json
import uuid
import os
import logging
import pytz
from datetime import datetime

log = logging.getLogger(__name__)
ET = pytz.timezone("America/New_York")
REPO_PATH = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_PATH = os.path.join(REPO_PATH, "portfolio.json")
TRADE_LOG_PATH = os.path.join(REPO_PATH, "trade_log.json")
CONTRACT_MULTIPLIER = 20  # $20 per point for NQ


def load_portfolio() -> dict:
    with open(PORTFOLIO_PATH, "r") as f:
        return json.load(f)


def save_portfolio(portfolio: dict) -> None:
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(portfolio, f, indent=2)


def load_trades() -> dict:
    with open(TRADE_LOG_PATH, "r") as f:
        return json.load(f)


def save_trades(trades: dict) -> None:
    with open(TRADE_LOG_PATH, "w") as f:
        json.dump(trades, f, indent=2)


def create_trade(
    strategy_key: str,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    contracts: int,
    reasoning: str,
) -> dict:
    return {
        "id": str(uuid.uuid4())[:8],
        "strategy": strategy_key,
        "direction": direction,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "contracts": contracts,
        "status": "open",
        "entry_time": datetime.now(ET).isoformat(),
        "exit_price": None,
        "exit_time": None,
        "pnl_points": None,
        "pnl_dollars": None,
        "reasoning": reasoning,
        "be_moved": False,
    }


def check_open_positions(
    current_price: float, portfolio: dict, trades: dict
) -> tuple[list, dict, dict]:
    """
    For every open position check TP / SL / BE.
    Returns (list_of_closed_ids, updated_portfolio, updated_trades).
    """
    closed = []
    open_ids = {t["id"] for t in portfolio.get("open_trades", [])}

    for trade in trades["trades"]:
        if trade["status"] != "open" or trade["id"] not in open_ids:
            continue

        entry = trade["entry"]
        sl = trade["sl"]
        tp = trade["tp"]
        direction = trade["direction"]
        contracts = trade["contracts"]
        strat_key = trade["strategy"]

        # --- Move SL to break-even when 1:1 is reached ---
        if not trade["be_moved"]:
            risk = abs(entry - sl)
            if direction == "long" and current_price >= entry + risk:
                trade["sl"] = entry
                trade["be_moved"] = True
                log.info(f"[{strat_key}] BE moved on trade {trade['id']}")
            elif direction == "short" and current_price <= entry - risk:
                trade["sl"] = entry
                trade["be_moved"] = True
                log.info(f"[{strat_key}] BE moved on trade {trade['id']}")

        sl = trade["sl"]  # refreshed after potential BE move

        hit_tp = (direction == "long" and current_price >= tp) or \
                 (direction == "short" and current_price <= tp)
        hit_sl = (direction == "long" and current_price <= sl) or \
                 (direction == "short" and current_price >= sl)

        if not hit_tp and not hit_sl:
            continue

        if hit_tp:
            exit_price = tp
            pnl_points = (tp - entry) if direction == "long" else (entry - tp)
            status = "closed_win"
        else:
            exit_price = sl
            pnl_points = (sl - entry) if direction == "long" else (entry - sl)
            status = "closed_be" if trade["be_moved"] and sl == entry else "closed_loss"

        pnl_dollars = round(pnl_points * CONTRACT_MULTIPLIER * contracts, 2)

        trade["status"] = status
        trade["exit_price"] = round(exit_price, 2)
        trade["exit_time"] = datetime.now(ET).isoformat()
        trade["pnl_points"] = round(pnl_points, 2)
        trade["pnl_dollars"] = pnl_dollars

        # Update strategy stats
        strat = portfolio["strategies"].get(strat_key, {})
        strat["balance"] = round(strat.get("balance", 50000) + pnl_dollars, 2)
        strat["pnl"] = round(strat.get("pnl", 0) + pnl_dollars, 2)
        if status == "closed_win":
            strat["wins"] = strat.get("wins", 0) + 1
        elif status == "closed_loss":
            strat["losses"] = strat.get("losses", 0) + 1
        total = strat.get("wins", 0) + strat.get("losses", 0)
        strat["win_rate"] = round(strat["wins"] / total, 3) if total > 0 else 0
        portfolio["strategies"][strat_key] = strat

        # Remove from open_trades list
        portfolio["open_trades"] = [
            t for t in portfolio.get("open_trades", []) if t["id"] != trade["id"]
        ]
        portfolio["last_updated"] = datetime.now(ET).strftime("%Y-%m-%d")
        closed.append(trade["id"])

        log.info(
            f"[{strat_key}] {status.upper()} trade {trade['id']} | "
            f"P&L: {pnl_points:+.2f} pts / ${pnl_dollars:+,.2f}"
        )

    return closed, portfolio, trades
