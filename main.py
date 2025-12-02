import os
import time
import hmac
import hashlib
import json

from fastapi import FastAPI, Request, HTTPException
import httpx

app = FastAPI()

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api-testnet.bybit.com")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "MY_SUPER_SECRET")


def bybit_sign(message: str, secret: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


async def bybit_private_post(path: str, body: dict):
    """Helper to send signed POST requests to Bybit V5"""
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

    url = f"{BYBIT_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, headers=headers, content=body_str)

    return response.json()


@app.post("/tv-webhook")
async def tv_webhook(request: Request):
    try:
        alert = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    print("Incoming alert:", alert)

    # 1️⃣ Validate secret
    if alert.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")

    # 2️⃣ Extract all parameters
    category = alert.get("category", "linear")
    symbol = alert.get("symbol")
    side = alert.get("side")
    qty = alert.get("qty")
    orderType = alert.get("orderType", "Market")
    tp = alert.get("takeProfit")
    sl = alert.get("stopLoss")

    if not all([symbol, side, qty]):
        raise HTTPException(status_code=400, detail="Missing symbol/side/qty")

    # 3️⃣ Send MARKET ORDER
    order_body = {
        "category": category,
        "symbol": symbol,
        "side": side,
        "orderType": orderType,
        "qty": str(qty),
        "timeInForce": "GTC"
    }

    print("Sending MARKET order:", order_body)
    order_res = await bybit_private_post("/v5/order/create", order_body)
    print("Order response:", order_res)

    if order_res.get("retCode") != 0:
        return {"error": "Failed to create order", "bybit": order_res}

    order_id = order_res["result"]["orderId"]
    print("Order ID:", order_id)

    # 4️⃣ Wait briefly to ensure position is open
    await asyncio.sleep(0.5)

    # 5️⃣ Apply TP/SL to the position (not to the order)
    if tp or sl:
        tpsl_body = {
            "category": category,
            "symbol": symbol,
            "takeProfit": str(tp) if tp else "",
            "stopLoss": str(sl) if sl else "",
            "tpOrderType": "Market",
            "slOrderType": "Market",
            # can enforce position side if needed:
            # "positionIdx": 1 for long, 2 for short
        }

        print("Applying TP/SL:", tpsl_body)
        tpsl_res = await bybit_private_post("/v5/position/trading-stop", tpsl_body)
        print("TP/SL response:", tpsl_res)

    return {
        "status": "ok",
        "orderId": order_id,
        "orderResponse": order_res,
        "tpSlResponse": tpsl_res if tp or sl else None
    }