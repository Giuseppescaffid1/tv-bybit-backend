import os
import time
import hmac
import hashlib
import json
 
from fastapi import FastAPI, Request, HTTPException
import httpx
 
app = FastAPI()
 
# Environment vars
BYBIT_API_KEY    = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL   = os.getenv("BYBIT_BASE_URL", "https://api-testnet.bybit.com")
WEBHOOK_SECRET   = os.getenv("WEBHOOK_SECRET", "MY_SUPER_SECRET")
 
 
def bybit_sign(message: str, secret: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
 
 
@app.post("/tv-webhook")
async def tv_webhook(request: Request):
    try:
        alert = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON")
 
    print("📥 Incoming alert:", alert)
 
    if alert.get("secret") != WEBHOOK_SECRET:
        print("❌ Invalid secret")
        raise HTTPException(401, "Invalid secret")
 
    category  = alert.get("category", "linear")
    symbol    = alert.get("symbol")
    side      = alert.get("side")
    qty       = alert.get("qty")
    orderType = alert.get("orderType", "Market")
 
    if not all([symbol, side, qty]):
        raise HTTPException(400, "Missing symbol/side/qty")
 
    body = {
        "category": category,
        "symbol": symbol,
        "side": side,
        "orderType": orderType,
        "qty": str(qty),
        "timeInForce": "GTC"
    }
 
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
        "X-BAPI-RECV-WINDOW": recvWindow,
    }
 
    url = f"{BYBIT_BASE_URL}/v5/order/create"
    print("🚀 Sending to Bybit:", url)
 
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=headers, content=body_str)
 
    print("📦 Bybit response:", r.text)
    return {"status": r.status_code, "body": r.text}
