import pandas as pd
from pybit.unified_trading import HTTP
from .state import market_data, trades, open_trade
from dataclasses import dataclass
from collections import deque
import time

SYMBOL = "ETHUSDT"
CATEGORY = "linear"
LIMIT = 10
LEVELS_FOR_DEPTH = 5

IMB_THRESHOLD = 0.18
MAX_SPREAD = 0.12
POSITION_SIZE_USDT = 1_000
FEE_RATE = 0.00065
TP_PCT = 0.0020
SL_PCT = 0.0012

session = HTTP(testnet=False)
imb_hist = deque(maxlen=12)

@dataclass
class Trade:
    side: str
    entry_price: float
    qty: float
    entry_ts: pd.Timestamp
    exit_price: float | None = None
    pnl: float | None = None

def fetch_orderbook():
    return session.get_orderbook(
        category=CATEGORY,
        symbol=SYMBOL,
        limit=LIMIT
    )["result"]

def step():
    global open_trade

    book = fetch_orderbook()

    bids = book["b"][:LEVELS_FOR_DEPTH]
    asks = book["a"][:LEVELS_FOR_DEPTH]

    bid_price = float(bids[0][0])
    ask_price = float(asks[0][0])

    mid = (bid_price + ask_price) / 2
    spread = ask_price - bid_price

    depth_bid = sum(float(x[1]) for x in bids)
    depth_ask = sum(float(x[1]) for x in asks)

    imb = (depth_bid - depth_ask) / max(depth_bid + depth_ask, 1)
    imb_hist.append(imb)
    imb_smooth = sum(imb_hist) / len(imb_hist)

    ts = pd.to_datetime(book["ts"], unit="ms")

    market_data.append({
        "ts": ts,
        "mid": mid,
        "imbalance": imb_smooth
    })

    # EXIT
    if open_trade:
        if open_trade.side == "LONG":
            if mid >= open_trade.entry_price * (1 + TP_PCT):
                pnl = (mid - open_trade.entry_price) * open_trade.qty
                open_trade.pnl = pnl
                trades.append(open_trade)
                open_trade = None

    # ENTRY
    if open_trade is None and spread <= MAX_SPREAD:
        if imb_smooth > IMB_THRESHOLD:
            qty = POSITION_SIZE_USDT / ask_price
            open_trade = Trade("LONG", ask_price, qty, ts)
