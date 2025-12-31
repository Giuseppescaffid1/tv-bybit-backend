# Troubleshooting: "Database is empty" on Render

## Quick Diagnosis

If you see `⚠️ Database is empty - data collector may not be running`, follow these steps:

### Step 1: Check Worker Service Status

1. Go to Render Dashboard
2. Find the **`bybit-data-collector`** service (worker type)
3. Check if it's **Running** (green status)
4. If it's stopped or crashed, click "Manual Deploy" to restart it

### Step 2: Check Worker Logs

1. Click on `bybit-data-collector` service
2. Go to "Logs" tab
3. Look for these messages:

**✅ Good signs:**
```
📦 STARTING DATA COLLECTOR WORKER
✅ Database connection successful
✅ Database tables initialized
✅ WebSocket connection opened
✅ Saved tick #1 to database
```

**❌ Bad signs:**
```
❌ Database connection failed
⚠️ No DATABASE_URL found, using SQLite
❌ WebSocket error
```

### Step 3: Verify DATABASE_URL is Set

**For the Worker Service (`bybit-data-collector`):**

1. Go to `bybit-data-collector` service → "Environment" tab
2. Check if `DATABASE_URL` exists
3. If missing:
   - Click "Add Environment Variable"
   - Key: `DATABASE_URL`
   - Value: Your PostgreSQL Internal Database URL (from your database service)
   - Click "Save Changes"
   - Service will auto-restart

**For the Web Service (`bybit-trading-dashboard`):**

1. Go to `bybit-trading-dashboard` service → "Environment" tab
2. Verify `DATABASE_URL` is set (same value as worker)

### Step 4: Check Database Service

1. Go to your PostgreSQL database service
2. Verify it's **Running** (not paused)
3. Copy the **Internal Database URL** (starts with `postgres://`)
4. Make sure both services use this URL

### Step 5: Test Database Connection

Visit your web app's health endpoint:
```
https://your-app.onrender.com/health
```

This will show:
- Database connection status
- Total ticks in database
- Recent ticks (last 10 minutes)
- Latest tick timestamp

### Step 6: Common Issues

#### Issue: Worker service not running
**Solution:** 
- Check if worker service exists in Render dashboard
- If missing, the `render.yaml` may not have deployed it
- Manually create a worker service or redeploy from `render.yaml`

#### Issue: DATABASE_URL not set
**Solution:**
- Set `DATABASE_URL` in both web and worker services
- Use the Internal Database URL from your PostgreSQL service
- Restart both services after setting

#### Issue: WebSocket connection fails
**Solution:**
- Check worker logs for WebSocket errors
- Verify internet connectivity (Render services can access external APIs)
- Check if Bybit WebSocket is accessible

#### Issue: Database connection fails
**Solution:**
- Verify `DATABASE_URL` is correct
- Ensure database is in same region as services
- Check database is not paused (free tier pauses after inactivity)
- Verify database service is running

### Step 7: Manual Verification

If everything looks correct but still no data:

1. **Check worker is actually running:**
   - Worker logs should show heartbeats every 60 seconds
   - Look for: `💓 Heartbeat #X - Collected Y ticks so far`

2. **Check database directly:**
   - Go to your PostgreSQL service → "Connect" → "psql"
   - Run: `SELECT COUNT(*) FROM orderbook_ticks;`
   - Should show > 0 if data is being collected

3. **Check web service can read:**
   - Visit `/health` endpoint
   - Should show `total_ticks > 0` if data exists

## Expected Log Flow

When everything works, you should see in worker logs:

```
============================================================
📦 STARTING DATA COLLECTOR WORKER
============================================================
🔗 Database URL configured: Yes
🔧 Testing database connection...
✅ Database connection successful
🔧 Initializing database tables...
✅ Database tables initialized
✅ Database has 1 table(s): ['orderbook_ticks']
🚀 Starting Bybit WebSocket data collector...
⏳ Waiting for WebSocket connection...
✅ WebSocket connection opened for ETHUSDT
✅ Subscription confirmed
✅ Saved tick #1 to database: price=XXXX.XX
✅ Saved tick #2 to database: price=XXXX.XX
...
💓 Heartbeat #1 - Collected 60 ticks so far
💓 Heartbeat #2 - Collected 120 ticks so far
📊 Database status: 120 total ticks stored
```

## Still Not Working?

1. **Check all services are running** (web, worker, database)
2. **Verify DATABASE_URL in both services** (web and worker)
3. **Check worker logs for errors**
4. **Verify database is not paused**
5. **Try restarting all services**

If still stuck, share:
- Worker service logs (last 50 lines)
- Web service logs (last 50 lines)
- Output from `/health` endpoint
- Screenshot of environment variables (hide sensitive parts)

