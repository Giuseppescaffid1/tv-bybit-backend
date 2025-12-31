# 🚀 Deploy to Render - Step by Step

Since your local testing works, follow these steps to deploy to Render.

## Prerequisites

✅ Local testing works
✅ Database connection works
✅ Data collector saves data
✅ Web dashboard shows data

## Step 1: Verify Your Code is Committed

```bash
# Check status
git status

# If you have uncommitted changes:
git add .
git commit -m "Ready for Render deployment - local testing passed"
git push
```

## Step 2: Set Up PostgreSQL Database on Render

1. **Go to Render Dashboard**: https://dashboard.render.com
2. **Create PostgreSQL Database**:
   - Click "New +" → "PostgreSQL"
   - **Name**: `bybit-orderbook-db` (or your preferred name)
   - **Database**: `orderbook_ctoz` (or auto-generated)
   - **Region**: Choose closest to you
   - Click "Create Database"
3. **Copy Database URL**:
   - Go to your database service
   - Click "Connect" → "Internal Database URL"
   - **Copy the URL** (starts with `postgres://`)

## Step 3: Deploy Services

### Option A: Using render.yaml (Automatic - Recommended)

1. **Go to Render Dashboard** → "New +" → "Blueprint"
2. **Connect your GitHub repository**
3. **Render will detect `render.yaml`** and create:
   - Web service: `bybit-trading-dashboard`
   - Worker service: `bybit-data-collector`
4. **Click "Apply"** to deploy

### Option B: Manual Setup

#### Create Web Service:

1. **Render Dashboard** → "New +" → "Web Service"
2. **Connect GitHub repository**
3. **Configure**:
   - **Name**: `bybit-trading-dashboard`
   - **Root Directory**: `liquidity-imbalance-strategy` (or leave empty if repo root)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd streamlit && python -c "from streamlit.database import init_db; init_db()" && gunicorn --bind 0.0.0.0:$PORT app:server`
   - **Python Version**: `3.11.0`
4. **Environment Variables**:
   - Add `DATABASE_URL` = (paste Internal Database URL from Step 2)
5. **Click "Create Web Service"**

#### Create Worker Service:

1. **Render Dashboard** → "New +" → "Background Worker"
2. **Connect GitHub repository**
3. **Configure**:
   - **Name**: `bybit-data-collector`
   - **Root Directory**: `liquidity-imbalance-strategy` (or leave empty)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd streamlit && python data_collector.py`
   - **Python Version**: `3.11.0`
4. **Environment Variables**:
   - Add `DATABASE_URL` = (same value as web service - Internal Database URL)
5. **Click "Create Background Worker"**

## Step 4: Configure Environment Variables

**For BOTH services** (web and worker):

1. Go to each service → "Environment" tab
2. Add environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Paste the **Internal Database URL** from your PostgreSQL service
   - **Important**: Use the **Internal** URL (not External) for services on Render
3. **Save Changes**
4. Services will auto-restart

## Step 5: Verify Deployment

### Check Web Service:

1. **Wait for deployment to complete** (usually 2-5 minutes)
2. **Visit your web service URL**: `https://your-app.onrender.com`
3. **Check health endpoint**: `https://your-app.onrender.com/health`
   - Should show JSON with database status
   - Initially may show `total_ticks: 0` (worker needs time to collect data)

### Check Worker Service:

1. **Go to worker service** → "Logs" tab
2. **Look for**:
   ```
   📦 STARTING DATA COLLECTOR WORKER
   ✅ Database connection successful
   ✅ Database tables initialized
   ✅ WebSocket connection opened
   ✅ Saved tick #1 to database
   ```

### Expected Timeline:

- **0-2 minutes**: Services deploy
- **2-5 minutes**: Worker connects and starts collecting
- **5-10 minutes**: Database has data, dashboard shows charts

## Step 6: Troubleshooting

### Issue: "Database is empty" on dashboard

**Check:**
1. Worker service is running (green status)
2. Worker logs show "✅ Saved tick #1 to database"
3. Both services have `DATABASE_URL` set (same value)
4. Wait 5-10 minutes for data to accumulate

**Solution:**
- Check worker service logs for errors
- Verify `DATABASE_URL` in both services
- Restart worker service if needed

### Issue: Worker service not collecting data

**Check worker logs for:**
- `❌ Database connection failed` → Check `DATABASE_URL`
- `❌ WebSocket error` → Check internet/Bybit connectivity
- `⚠️ No DATABASE_URL found` → Add `DATABASE_URL` environment variable

**Solution:**
- Verify `DATABASE_URL` is set in worker service
- Use Internal Database URL (not External)
- Restart worker service

### Issue: Web service can't connect to database

**Check:**
- `DATABASE_URL` is set in web service
- Database service is running (not paused)
- Using Internal Database URL

**Solution:**
- Add/update `DATABASE_URL` in web service
- Restart web service

## Step 7: Monitor Deployment

### Web Service Logs:
- Check for: `✅ Database connection successful`
- Check for: `✅ Retrieved X ticks from database`

### Worker Service Logs:
- Check for: `✅ Saved tick #1 to database`
- Check for: `💓 Heartbeat #X - Collected Y ticks so far`
- Check for: `📊 Database status: X total ticks stored`

### Health Endpoint:
Visit: `https://your-app.onrender.com/health`

Should show:
```json
{
  "status": "ok",
  "total_ticks": 100,
  "recent_ticks_10min": 100,
  "worker_status": "✅ Running (collecting data)"
}
```

## Quick Checklist

Before deploying:
- [ ] Code committed and pushed to GitHub
- [ ] Local testing works
- [ ] `.env` file is gitignored (won't be deployed)

After deploying:
- [ ] PostgreSQL database created on Render
- [ ] Web service deployed and running
- [ ] Worker service deployed and running
- [ ] `DATABASE_URL` set in both services (Internal URL)
- [ ] Worker logs show "✅ Saved tick #1"
- [ ] Web dashboard shows data (not "waiting for live data")
- [ ] Health endpoint shows `total_ticks > 0`

## Important Notes

1. **Use Internal Database URL** for services on Render (not External)
2. **Both services need `DATABASE_URL`** (web and worker)
3. **Worker service must be running** for data collection
4. **Wait 5-10 minutes** after deployment for data to accumulate
5. **Free tier services** may spin down after inactivity - first request may be slow

## Next Steps

Once deployed and working:
1. ✅ Monitor logs for any errors
2. ✅ Check health endpoint regularly
3. ✅ Verify data is being collected
4. ✅ Set up monitoring/alerts if needed

