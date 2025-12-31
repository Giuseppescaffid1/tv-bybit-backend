# ⚠️ CRITICAL: Worker Service Not Collecting Data

## Current Status
- ✅ Web service is running and can connect to database
- ✅ DATABASE_URL is configured (length: 107)
- ❌ Database is empty (0 ticks)
- ❌ Worker service is NOT collecting data

## Immediate Action Required

### Step 1: Check if Worker Service Exists
1. Go to Render Dashboard: https://dashboard.render.com
2. Look for a service named **`bybit-data-collector`** (type: Worker)
3. If it doesn't exist, the worker service was never created

### Step 2: If Worker Service Doesn't Exist

**Option A: Create it manually**
1. Render Dashboard → "New +" → "Background Worker"
2. Connect your GitHub repository
3. Configure:
   - **Name**: `bybit-data-collector`
   - **Root Directory**: `liquidity-imbalance-strategy` (or leave empty if repo root)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd streamlit && python data_collector.py`
   - **Python Version**: `3.11.0`
4. **Environment Variables**:
   - Add `DATABASE_URL` = (same value as your web service)
   - Get it from: PostgreSQL service → "Connect" → "Internal Database URL"
5. Click "Create Background Worker"

**Option B: Redeploy from render.yaml**
1. Render Dashboard → "New +" → "Blueprint"
2. Connect your GitHub repository
3. Render will detect `render.yaml` and create both services
4. Make sure to set `DATABASE_URL` in the worker service after creation

### Step 3: If Worker Service Exists

1. **Check Status**:
   - Is it "Running" (green) or "Stopped" (red)?
   - If stopped, click "Manual Deploy" to restart

2. **Check Environment Variables**:
   - Go to worker service → "Environment" tab
   - Verify `DATABASE_URL` exists
   - If missing, add it (same value as web service)

3. **Check Logs**:
   - Go to worker service → "Logs" tab
   - Look for these messages:

**✅ Good signs:**
```
📦 STARTING DATA COLLECTOR WORKER
✅ Database connection successful
✅ Database tables initialized
✅ WebSocket connection opened
✅ Saved tick #1 to database
💓 Heartbeat #1 - Collected 60 ticks so far
```

**❌ Bad signs:**
```
❌ Database connection failed
⚠️ No DATABASE_URL found, using SQLite
❌ WebSocket error
```

### Step 4: Common Issues

#### Issue: Worker service not in dashboard
**Solution**: Create it manually (see Step 2)

#### Issue: DATABASE_URL not set in worker
**Solution**: 
- Get Internal Database URL from PostgreSQL service
- Add it to worker service → Environment → `DATABASE_URL`
- Restart worker service

#### Issue: Worker crashes on startup
**Solution**: 
- Check logs for error messages
- Common causes:
  - Missing `DATABASE_URL`
  - Database connection failed
  - Import errors (check `from streamlit.database import ...`)

#### Issue: Worker runs but no data saved
**Solution**:
- Check logs for "✅ Saved tick" messages
- If you see "Collected X ticks" but database is empty, there's a save error
- Check logs for database save errors

## Verification

After fixing, verify:

1. **Worker logs show**:
   ```
   ✅ Saved tick #1 to database
   💓 Heartbeat #1 - Collected 60 ticks so far
   ```

2. **Web service `/health` endpoint shows**:
   ```json
   {
     "total_ticks": 60,
     "recent_ticks_10min": 60,
     "worker_status": "✅ Running (collecting data)"
   }
   ```

3. **Dashboard shows data** instead of "waiting for live data"

## Quick Test

Visit: `https://your-app.onrender.com/health`

This will show:
- Database connection status
- Total ticks in database
- Recent ticks count
- Worker status diagnosis

If `total_ticks: 0`, the worker is definitely not saving data.

