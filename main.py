"""
NQ Paper Trading Bot
Runs every 5 minutes during market hours.
Checks all 4 strategy agents for signals, manages open positions,
and auto-commits results to GitHub.
"""

import logging
import time
import pytz
import schedule
from datetime import datetime

from data_feed import get_current_price
from trade_manager import load_portfolio, load_trades, check_open_positions, save_portfolio, save_trades
from github_logger import git_push
from strategies.day_trade import DayTradeStrategy
from strategies.swing import SwingStrategy
from strategies.strat1 import Strat1
from strategies.strat2 import Strat2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

STRATEGIES = [
    DayTradeStrategy(),
    SwingStrategy(),
    Strat1(),
    Strat2(),
]


def is_market_open() -> bool:
    """NQ futures trade Sun 6 pm – Fri 5 pm ET with a daily 5–6 pm break."""
    now = datetime.now(ET)
    wd = now.weekday()  # 0=Mon … 6=Sun
    h, m = now.hour, now.minute

    if wd == 5:            # Saturday: always closed
        return False
    if wd == 6:            # Sunday: open from 6 pm ET
        return h >= 18
    if wd == 4:            # Friday: closes at 5 pm ET
        return h < 17
    if 17 <= h < 18:       # Daily maintenance break 5–6 pm ET
        return False
    return True


def run_cycle() -> None:
    """One full scan: manage positions, then check for new signals."""
    if not is_market_open():
        log.info("Market closed — skipping cycle")
        return

    price = get_current_price()
    if price is None:
        log.warning("Could not fetch current price — skipping cycle")
        return

    log.info(f"─── Cycle | NQ @ {price:,.2f} | {datetime.now(ET).strftime('%H:%M ET')} ───")

    portfolio = load_portfolio()
    trades = load_trades()
    changed = False

    # 1. Manage existing open positions
    closed, portfolio, trades = check_open_positions(price, portfolio, trades)
    if closed:
        changed = True

    # 2. Check each strategy for a new signal
    for strategy in STRATEGIES:
        try:
            signal = strategy.check_signal(portfolio, trades)
            if signal is None:
                continue

            trade = strategy.open_trade(signal, portfolio, trades)
            trades["trades"].append(trade)

            strat = portfolio["strategies"].setdefault(strategy.portfolio_key, {})
            strat["total_trades"] = strat.get("total_trades", 0) + 1

            portfolio.setdefault("open_trades", []).append(
                {"id": trade["id"], "strategy": strategy.portfolio_key}
            )
            portfolio["last_updated"] = datetime.now(ET).strftime("%Y-%m-%d")
            changed = True

            log.info(
                f"[{strategy.name}] SIGNAL → {trade['direction'].upper()} "
                f"entry={trade['entry']:,.2f}  SL={trade['sl']:,.2f}  TP={trade['tp']:,.2f}"
            )
            log.info(f"  reason: {trade['reasoning']}")

        except Exception:
            log.exception(f"[{strategy.name}] Error during signal check")

    # 3. Persist and push to GitHub if anything changed
    if changed:
        save_portfolio(portfolio)
        save_trades(trades)
        git_push()


def main() -> None:
    log.info("═══ NQ Paper Trading Bot starting ═══")
    run_cycle()                                  # immediate first run

    schedule.every(5).minutes.do(run_cycle)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
