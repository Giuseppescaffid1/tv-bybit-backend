import os
import time
import hmac
import hashlib
import json
import asyncio

from fastapi import FastAPI, Request, HTTPException
import httpx

app = FastAPI()

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "MY_SUPER_SECRET")


def bybit_sign(message: str, secret: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


async def bybit_private_post(path: str, body: dict):
    body_str = json.dumps(body)
    timestamp = str(int(time.time() * 1000))
    recvWindow = "5000"

    pre_sign = timestamp + BYBIT_API_KEY + recvWindow + body_str
    signature = bybit_sign(pre_sign, BYBIT_API_SECRET)

    headers = {
        "Content-Type": "application/json",
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recvWindow
    }

    url = BYBIT_BASE_URL + path

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, headers=headers, content=body_str)

    return response.json()


async def get_position(symbol: str):
    url = f"{BYBIT_BASE_URL}/v5/position/list"
    params = {"category": "linear", "symbol": symbol}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    data = r.json()

    if data["retCode"] != 0:
        return None

    pos = data["result"]["list"][0]
    return pos


async def close_existing_position(symbol: str):
    pos = await get_position(symbol)

    if not pos:
        print("⚠️ Cannot fetch position")
        return

    size = float(pos["size"])
    if size == 0:
        print(f"✔️ No open position on {symbol}, nothing to close.")
        return

    side = pos["side"]  # "Buy" or "Sell"
    close_side = "Sell" if side == "Buy" else "Buy"

    close_body = {
        "category": "linear",
        "symbol": symbol,
        "side": close_side,
        "orderType": "Market",
        "qty": str(size),
        "reduceOnly": True
    }

    print(f"🔴 Closing previous position: {close_body}")
    res = await bybit_private_post("/v5/order/create", close_body)
    print("Close response:", res)
    await asyncio.sleep(0.5)  # give Bybit time to update


@app.post("/tv-webhook")
async def tv_webhook(request: Request):
    # 1️⃣ Parse webhook
    try:
        alert = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    print("Incoming alert:", alert)

    if alert.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    category = alert.get("category", "linear")
    symbol = alert.get("symbol")
    side = alert.get("side")
    qty = alert.get("qty")
    orderType = alert.get("orderType", "Market")
    tp = alert.get("takeProfit")
    sl = alert.get("stopLoss")

    if not all([symbol, side, qty]):
        raise HTTPException(status_code=400, detail="Missing symbol/side/qty")

    # 2️⃣ CLOSE ANY EXISTING POSITION FIRST
    await close_existing_position(symbol)

    # 3️⃣ OPEN NEW POSITION
    order_body = {
        "category": category,
        "symbol": symbol,
        "side": side,
        "orderType": orderType,
        "qty": str(qty),
        "timeInForce": "GTC"
    }

    print("🟢 Opening new position:", order_body)
    order_res = await bybit_private_post("/v5/order/create", order_body)
    print("New order response:", order_res)

    if order_res.get("retCode") != 0:
        return {"error": "Failed to open new order", "bybit": order_res}

    order_id = order_res["result"]["orderId"]

    # 4️⃣ APPLY TP/SL
    if tp or sl:
        tpsl_body = {
            "category": category,
            "symbol": symbol,
            "takeProfit": str(tp) if tp else "",
            "stopLoss": str(sl) if sl else "",
            "tpOrderType": "Market",
            "slOrderType": "Market"
        }
        print("🎯 Applying TP/SL:", tpsl_body)
        tpsl_res = await bybit_private_post("/v5/position/trading-stop", tpsl_body)
    else:
        tpsl_res = None

    return {
        "status": "ok",
        "orderId": order_id,
        "orderResponse": order_res,
        "tpSlResponse": tpsl_res
    }