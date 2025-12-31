# Database-Based Architecture

This app now uses a **database-backed architecture** instead of direct WebSocket connections in the web app.

## Architecture Overview

```
┌─────────────────────┐
│  Bybit WebSocket    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Data Collector     │  ← Background Worker (data_collector.py)
│  (Worker Service)   │     Continuously collects data
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  PostgreSQL DB      │  ← Stores all orderbook ticks
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Web Dashboard      │  ← Reads from database (app.py)
│  (Web Service)      │     Shows data with small lag
└─────────────────────┘
```

## Setup Steps

### 1. Create PostgreSQL Database on Render

1. Go to Render Dashboard → "New +" → "PostgreSQL"
2. Name it: `bybit-orderbook-db`
3. Copy the **Internal Database URL** (starts with `postgres://`)

### 2. Set Environment Variable

For **BOTH** services (web and worker):

1. Go to each service → "Environment"
2. Add: `DATABASE_URL` = (paste the Internal Database URL)
3. **Important**: Change `postgres://` to `postgresql://` in the URL

### 3. Deploy

The `render.yaml` will create:
- **Web Service**: Dashboard (reads from DB)
- **Worker Service**: Data collector (writes to DB)

## How It Works

1. **Worker** (`data_collector.py`):
   - Connects to Bybit WebSocket
   - Collects orderbook ticks every second
   - Saves to PostgreSQL database
   - Runs continuously in background

2. **Web App** (`app.py`):
   - Reads from database (not WebSocket)
   - Shows last 10 minutes of data
   - Updates every 1 second
   - More reliable and stable

## Benefits

✅ **Reliability**: Data persists even if WebSocket disconnects  
✅ **Separation**: Data collection separate from web serving  
✅ **Scalability**: Can add more workers or web instances  
✅ **History**: Data stored for analysis  
✅ **No WebSocket issues**: Web app doesn't need WebSocket connection

## Data Lag

- **Typical lag**: 1-5 seconds
- **Maximum lag**: ~10 seconds (if worker is slow)
- Data is stored with timestamps, so you can see exactly when it was collected

## Monitoring

- **Worker logs**: Check data collection status
- **Web logs**: Check database queries
- **Database**: Monitor size and query performance

## Files

- `streamlit/database.py` - Database models and utilities
- `streamlit/data_collector.py` - Background worker
- `streamlit/app.py` - Web dashboard (reads from DB)
- `render.yaml` - Render configuration (web + worker)

