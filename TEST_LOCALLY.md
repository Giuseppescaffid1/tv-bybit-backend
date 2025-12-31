# 🧪 How to Test Locally

## Step 1: Verify Setup

Make sure you have:
- ✅ `.env` file in project root with `DATABASE_URL`
- ✅ Dependencies installed: `pip install -r requirements.txt`

**Quick check:**
```bash
# Check .env exists
ls -la .env

# Test database connection
cd streamlit
PYTHONPATH=.. python -c "from streamlit.database import init_db; init_db(); print('✅ Database OK')"
```

## Step 2: Run Data Collector (Terminal 1)

Open your first terminal and run:

```bash
cd streamlit
PYTHONPATH=.. python data_collector.py
```

**What you should see:**
```
============================================================
📦 STARTING DATA COLLECTOR WORKER
============================================================
✅ Database connection successful
✅ Database tables initialized
✅ WebSocket connection opened
✅ Saved tick #1 to database
💓 Heartbeat #1 - Collected 60 ticks so far
```

**✅ Success indicators:**
- No error messages
- See "✅ Saved tick #1 to database" within 5-10 seconds
- Heartbeat messages every 60 seconds showing tick count

**❌ If you see errors:**
- `ModuleNotFoundError`: Run `pip install -r requirements.txt`
- `Database connection failed`: Check `.env` file has correct `DATABASE_URL`
- `WebSocket error`: Check internet connection

## Step 3: Run Web Dashboard (Terminal 2)

Open a **second terminal** and run:

```bash
cd streamlit
PYTHONPATH=.. python app.py
```

**What you should see:**
```
Dash is running on http://127.0.0.1:8050/
```

**Then:**
1. Open your browser: **http://localhost:8050**
2. You should see:
   - Charts with data (not "waiting for live data")
   - Orderbook table with recent ticks
   - Stats showing trades/signals
   - Status indicator: "✅ Live data"

## Step 4: Verify Everything Works

### Check 1: Data Collector is Saving Data

In Terminal 1, wait 30 seconds, then you should see:
```
💓 Heartbeat #1 - Collected 60 ticks so far
```

### Check 2: Database Has Data

In a new terminal:
```bash
cd streamlit
PYTHONPATH=.. python -c "from streamlit.database import get_session, OrderbookTick; s = get_session(); count = s.query(OrderbookTick).count(); print(f'📊 Total ticks in database: {count}')"
```

Should show: `📊 Total ticks in database: X` (where X > 0)

### Check 3: Web Dashboard Shows Data

1. Visit: **http://localhost:8050**
2. Should see charts with data, not "waiting for live data"
3. Orderbook table should show recent ticks

### Check 4: Health Endpoint

Visit: **http://localhost:8050/health**

Should show JSON like:
```json
{
  "status": "ok",
  "total_ticks": 100,
  "recent_ticks_10min": 100,
  "worker_status": "✅ Running (collecting data)"
}
```

## Quick Test Scripts

### Option A: Use Test Scripts

```bash
# Test data collector (runs until Ctrl+C)
./test_collector.sh

# Test web app (runs until Ctrl+C)
./test_app.sh
```

### Option B: Manual (Two Terminals)

**Terminal 1:**
```bash
cd streamlit
PYTHONPATH=.. python data_collector.py
```

**Terminal 2:**
```bash
cd streamlit
PYTHONPATH=.. python app.py
```

Then open: **http://localhost:8050**

## Troubleshooting

### Issue: "Module not found: streamlit"

**Solution:** Use `PYTHONPATH=..` before python commands, or run from project root:
```bash
python -m streamlit.data_collector
```

### Issue: "Database connection failed"

**Solution:**
1. Check `.env` file exists: `ls -la .env`
2. Verify `DATABASE_URL` is set: `cat .env | grep DATABASE_URL`
3. Test connection: `psql "your-database-url"` (if psql installed)

### Issue: "No data showing in dashboard"

**Solution:**
1. Make sure data collector is running (Terminal 1)
2. Wait 30-60 seconds for data to accumulate
3. Check Terminal 1 logs for "✅ Saved tick" messages
4. Verify database has data (Check 2 above)

### Issue: "WebSocket connection failed"

**Solution:**
- Check internet connection
- Verify Bybit WebSocket is accessible
- Check firewall settings
- Wait a few seconds and try again (WebSocket may need time to connect)

## Expected Timeline

- **0-5 seconds**: Data collector connects to database and WebSocket
- **5-10 seconds**: First tick saved to database
- **30 seconds**: ~30 ticks collected
- **60 seconds**: First heartbeat message
- **Dashboard**: Should show data within 30-60 seconds

## Next Steps After Local Testing

Once everything works locally:

1. ✅ All tests pass
2. Commit changes: `git add . && git commit -m "Ready for deployment"`
3. Push to GitHub: `git push`
4. Render will auto-deploy
5. Verify on Render: `https://your-app.onrender.com/health`

## Quick Reference

| Service | Command | URL |
|---------|---------|-----|
| Data Collector | `cd streamlit && PYTHONPATH=.. python data_collector.py` | - |
| Web Dashboard | `cd streamlit && PYTHONPATH=.. python app.py` | http://localhost:8050 |
| Health Check | - | http://localhost:8050/health |

