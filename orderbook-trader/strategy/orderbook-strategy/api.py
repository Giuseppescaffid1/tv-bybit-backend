from fastapi import FastAPI
from state import market_data, trades, open_trade

app = FastAPI()

@app.get("/series")
def series():
    return list(market_data)

@app.get("/trades")
def get_trades():
    return trades

@app.get("/status")
def status():
    return {
        "open_trade": open_trade is not None,
        "trades": len(trades)
    }
