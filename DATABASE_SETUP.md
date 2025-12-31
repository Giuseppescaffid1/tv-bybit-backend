# Database Setup for Render

This app uses a PostgreSQL database to store orderbook data. The data is collected by a background worker and displayed by the web app.

## Setup on Render

### 1. Create PostgreSQL Database

1. Go to Render Dashboard → "New +" → "PostgreSQL"
2. Configure:
   - **Name**: `bybit-orderbook-db` (or your preferred name)
   - **Database**: `orderbook`
   - **User**: Auto-generated
   - **Region**: Choose closest to you
3. Click "Create Database"
4. **Important**: Copy the **Internal Database URL** (starts with `postgres://`)

### 2. Configure Environment Variables

For **both** services (web and worker):

1. Go to your service → "Environment"
2. Add environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Paste the Internal Database URL from step 1
3. Save changes

### 3. Deploy Services

The `render.yaml` will automatically create:
- **Web Service**: Dashboard that reads from database
- **Worker Service**: Background data collector

Both services will use the same `DATABASE_URL` environment variable.

## How It Works

1. **Data Collector Worker** (`data_collector.py`):
   - Connects to Bybit WebSocket
   - Collects orderbook ticks
   - Stores them in PostgreSQL database
   - Runs continuously in background

2. **Web Dashboard** (`app.py`):
   - Reads data from database (not WebSocket)
   - Shows data with a small lag (typically 1-5 seconds)
   - More reliable than direct WebSocket connection

## Benefits

- ✅ **Reliability**: Database persists data even if WebSocket disconnects
- ✅ **Separation**: Data collection separate from web serving
- ✅ **Scalability**: Can add more workers or web instances
- ✅ **History**: Data is stored for analysis

## Monitoring

- Check worker logs to see data collection status
- Check web logs to see database queries
- Monitor database size in Render dashboard

## Troubleshooting

**No data showing:**
- Check worker service is running
- Check worker logs for WebSocket connection
- Verify `DATABASE_URL` is set in both services
- Check database has data: `SELECT COUNT(*) FROM orderbook_ticks;`

**Database connection errors:**
- Verify `DATABASE_URL` is correct
- Ensure database is in same region as services
- Check database is not paused (free tier pauses after inactivity)

