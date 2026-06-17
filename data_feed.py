import yfinance as yf
import pandas as pd
import logging

log = logging.getLogger(__name__)
TICKER = "NQ=F"


def get_data(interval="5m", days=5) -> pd.DataFrame:
    """Fetch OHLCV data for NQ futures at the given interval."""
    try:
        ticker = yf.Ticker(TICKER)
        if interval in ("1m", "2m", "5m", "15m", "30m", "60m", "1h", "90m"):
            df = ticker.history(period=f"{days}d", interval=interval)
        elif interval == "1d":
            df = ticker.history(period="365d", interval="1d")
        elif interval == "1wk":
            df = ticker.history(period="104wk", interval="1wk")
        else:
            df = ticker.history(period=f"{days}d", interval=interval)

        if df.empty:
            log.warning(f"No data returned for {TICKER} {interval}")
            return df

        # Normalise timezone to Eastern
        if df.index.tz is None:
            df.index = df.index.tz_localize("America/New_York")
        else:
            df.index = df.index.tz_convert("America/New_York")

        return df

    except Exception as e:
        log.error(f"data_feed error ({interval}): {e}")
        return pd.DataFrame()


def get_4h_data() -> pd.DataFrame:
    """Return 4-hour bars by resampling 1-hour data."""
    df_1h = get_data("1h", 30)
    if df_1h.empty:
        return df_1h

    df_4h = df_1h.resample("4h").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Volume=("Volume", "sum"),
    ).dropna()

    return df_4h


def get_current_price() -> float | None:
    """Return the latest NQ price."""
    try:
        info = yf.Ticker(TICKER).fast_info
        price = info.get("last_price") or info.get("lastPrice")
        if price:
            return float(price)
    except Exception:
        pass

    df = get_data("1m", 1)
    if not df.empty:
        return float(df["Close"].iloc[-1])

    return None
