# Local Testing Guide

This guide helps you test the application locally before deploying to Render.

## Prerequisites

1. Python 3.11 installed
2. All dependencies installed: `pip install -r requirements.txt`
3. PostgreSQL database accessible (use External Database URL for local testing)

## Setup

### Step 1: Create .env file

Create a `.env` file in the project root with your database credentials:

```bash
# .env file (already created for you)
DATABASE_URL=postgresql://orderbook_ctoz_user:WSS3XtPCqndwSskDJZN5MvyJCcnWjarx@dpg-d5a7jejuibrs73bmm1mg-a.frankfurt-postgres.render.com:5432/orderbook_ctoz
```

**Note**: The `.env` file is gitignored, so your credentials are safe.

### Step 2: Test Database Connection

Run this to verify database connection:

```bash
cd streamlit
python -c "from streamlit.database import init_db, get_session, OrderbookTick; init_db(); session = get_session(); print(f'✅ Database connected! Tables: {session.query(OrderbookTick).count()} ticks')"
```

You should see:
```
✅ Using DATABASE_URL from environment (length: XXX)
✅ Database tables initialized
✅ Database connected! Tables: X ticks
```

## Running Locally

### Option 1: Run Both Services (Recommended)

Open **two terminal windows**:

**Terminal 1 - Data Collector:**
```bash
cd streamlit
python data_collector.py
```

You should see:
```
📦 STARTING DATA COLLECTOR WORKER
✅ Database connection successful
✅ Database tables initialized
✅ WebSocket connection opened
✅ Saved tick #1 to database
```

**Terminal 2 - Web Dashboard:**
```bash
cd streamlit
python app.py
```

Then open: http://localhost:8050

### Option 2: Use the Test Scripts

**Test Data Collector:**
```bash
./test_collector.sh
```

**Test Web App:**
```bash
./test_app.sh
```

## Verification

### 1. Check Data Collector is Working

In Terminal 1 (data collector), you should see:
- `✅ Saved tick #1 to database`
- `💓 Heartbeat #1 - Collected 60 ticks so far`
- No error messages

### 2. Check Database Has Data

```bash
cd streamlit
python -c "from streamlit.database import get_session, OrderbookTick; session = get_session(); count = session.query(OrderbookTick).count(); print(f'Total ticks: {count}')"
```

Should show: `Total ticks: X` (where X > 0)

### 3. Check Web Dashboard

1. Open http://localhost:8050
2. You should see:
   - Charts with data
   - Orderbook table with recent ticks
   - Stats showing trades/signals
   - Status indicator showing "✅ Live data"

### 4. Check Health Endpoint

Visit: http://localhost:8050/health

Should show JSON with:
```json
{
  "status": "ok",
  "total_ticks": 100,
  "recent_ticks_10min": 100,
  "worker_status": "✅ Running (collecting data)"
}
```

## Troubleshooting

### Issue: "No DATABASE_URL found, using SQLite"

**Solution**: Make sure `.env` file exists in project root with `DATABASE_URL` set.

### Issue: "Database connection failed"

**Solution**: 
- Verify External Database URL is correct
- Check if database is accessible from your IP (Render may require IP whitelist)
- Try connecting with psql: `psql "postgresql://orderbook_ctoz_user:WSS3XtPCqndwSskDJZN5MvyJCcnWjarx@dpg-d5a7jejuibrs73bmm1mg-a.frankfurt-postgres.render.com:5432/orderbook_ctoz"`

### Issue: "WebSocket connection failed"

**Solution**: 
- Check internet connection
- Verify Bybit WebSocket is accessible
- Check firewall settings

### Issue: "Module not found: streamlit.database"

**Solution**: 
- Make sure you're in the `streamlit` directory or project root
- Run: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"`

## Testing Checklist

Before deploying to Render, verify:

- [ ] Data collector connects to database
- [ ] Data collector saves ticks (check logs for "✅ Saved tick")
- [ ] Database has data (run count query)
- [ ] Web app loads at http://localhost:8050
- [ ] Web app shows data (not "waiting for live data")
- [ ] Health endpoint shows data
- [ ] Charts update in real-time
- [ ] Orderbook table shows recent ticks

## Next Steps

Once local testing passes:
1. Commit your changes
2. Push to GitHub
3. Render will auto-deploy
4. Verify on Render using `/health` endpoint

