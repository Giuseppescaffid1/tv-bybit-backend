import os
import time
import hmac
import hashlib
import json
import asyncio

from fastapi import FastAPI, Request, HTTPException
import httpx

# ==========================================================
# App
# ==========================================================
app = FastAPI()

# ==========================================================
# ENV VARS (Render / Local)
# ==========================================================
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api.bybit.com")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "MY_SUPER_SECRET")

if not BYBIT_API_KEY or not BYBIT_API_SECRET:
    raise RuntimeError("Missing BYBIT_API_KEY or BYBIT_API_SECRET")

# ==========================================================
# Signing
# ==========================================================
def bybit_sign(message: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

# ==========================================================
# Bybit PRIVATE POST
# ==========================================================
async def bybit_private_post(path: str, body: dict):
    body_str = json.dumps(body, separators=(",", ":"))
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    pre_sign = timestamp + BYBIT_API_KEY + recv_window + body_str
    signature = bybit_sign(pre_sign, BYBIT_API_SECRET)

    headers = {
        "Content-Type": "application/json",
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
    }

    url = BYBIT_BASE_URL + path

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=headers, content=body_str)

    try:
        return r.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=f"Bybit POST invalid response ({r.status_code}): {r.text}"
        )

# ==========================================================
# Bybit PRIVATE GET
# ==========================================================
async def bybit_private_get(path: str, params: dict):
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    query_str = "&".join(f"{k}={v}" for k, v in params.items())
    pre_sign = timestamp + BYBIT_API_KEY + recv_window + query_str
    signature = bybit_sign(pre_sign, BYBIT_API_SECRET)

    headers = {
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
    }

    url = BYBIT_BASE_URL + path

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers, params=params)

    try:
        return r.json()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=f"Bybit GET invalid response ({r.status_code}): {r.text}"
        )

# ==========================================================
# Get current position
# ==========================================================
async def get_position(symbol: str):
    params = {
        "category": "linear",
        "symbol": symbol
    }

    data = await bybit_private_get("/v5/position/list", params)

    if data.get("retCode") != 0:
        print("Bybit position error:", data)
        return None

    pos_list = data["result"]["list"]
    if not pos_list:
        return None

    return pos_list[0]

# ==========================================================
# Close existing position (reduceOnly)
# ==========================================================
async def close_existing_position(symbol: str):
    pos = await get_position(symbol)

    if not pos:
        print(f"✔️ No position on {symbol}")
        return

    size = float(pos.get("size", 0))
    if size == 0:
        print(f"✔️ Position size is zero on {symbol}")
        return

    side = pos["side"]  # Buy / Sell
    close_side = "Sell" if side == "Buy" else "Buy"

    close_body = {
        "category": "linear",
        "symbol": symbol,
        "side": close_side,
        "orderType": "Market",
        "qty": str(size),
        "reduceOnly": True
    }

    print("🔴 Closing position:", close_body)
    res = await bybit_private_post("/v5/order/create", close_body)
    print("Close response:", res)

    await asyncio.sleep(0.5)

# ==========================================================
# TradingView Webhook
# ==========================================================
@app.post("/tv-webhook")
async def tv_webhook(request: Request):
    try:
        alert = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    print("📩 Incoming alert:", alert)

    if alert.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    symbol = alert.get("symbol")
    side = alert.get("side")
    qty = alert.get("qty")

    category = alert.get("category", "linear")
    order_type = alert.get("orderType", "Market")
    tp = alert.get("takeProfit")
    sl = alert.get("stopLoss")

    if not all([symbol, side, qty]):
        raise HTTPException(status_code=400, detail="Missing symbol / side / qty")

    # 1️⃣ Close existing position
    await close_existing_position(symbol)

    # 2️⃣ Open new position
    # 3️⃣ Apply TP / SL
    order_body = {
        "category": category,
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": str(qty),
        "takeProfit": str(tp) if tp else "",
        "stopLoss": str(sl) if sl else "",
        "timeInForce": "GTC"
    }

    print("🟢 Opening position:", order_body)
    print("🎯 Setting TP/SL:", "TakeProfit:", tp, "StopLoss:", sl)
    order_res = await bybit_private_post("/v5/order/create", order_body)
    print("Order response:", order_res)

    if order_res.get("retCode") != 0:
        return {
            "status": "error",
            "bybit": order_res
        }

    order_id = order_res["result"]["orderId"]


    return {
        "status": "ok",
        "orderId": order_id,
        "orderResponse": order_res
    }

# ==========================================================
# Health check
# ==========================================================
@app.get("/")
async def root():
    return {"status": "running"}
