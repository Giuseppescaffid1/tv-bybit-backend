# Quick Start: Local Testing

## One-Time Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run setup script (creates .env file)
./setup_local.sh
```

## Running Locally

### Option 1: Two Terminal Windows (Recommended)

**Terminal 1 - Data Collector:**
```bash
cd streamlit
PYTHONPATH=.. python data_collector.py
```

**Terminal 2 - Web Dashboard:**
```bash
cd streamlit
PYTHONPATH=.. python app.py
```

Then open: **http://localhost:8050**

### Option 2: Use Test Scripts

```bash
# Test data collector (runs for 30 seconds)
./test_collector.sh

# Test web app (runs until Ctrl+C)
./test_app.sh
```

## Quick Verification

1. **Check database connection:**
   ```bash
   cd streamlit
   PYTHONPATH=.. python -c "from streamlit.database import init_db; init_db(); print('✅ OK')"
   ```

2. **Check if data is being collected:**
   - Look at Terminal 1 (data collector) for: `✅ Saved tick #1 to database`
   - Wait 30 seconds, then check database:
     ```bash
     cd streamlit
     PYTHONPATH=.. python -c "from streamlit.database import get_session, OrderbookTick; s = get_session(); print(f'Ticks: {s.query(OrderbookTick).count()}')"
     ```

3. **Check web dashboard:**
   - Open http://localhost:8050
   - Should see charts with data (not "waiting for live data")

4. **Check health endpoint:**
   - Visit http://localhost:8050/health
   - Should show JSON with `total_ticks > 0`

## Troubleshooting

**"Module not found: streamlit"**
- Use `PYTHONPATH=..` before python commands
- Or run from project root: `python -m streamlit.data_collector`

**"Database connection failed"**
- Check `.env` file exists with `DATABASE_URL`
- Verify External Database URL is correct
- Check internet connection

**"No data showing"**
- Make sure data collector is running (Terminal 1)
- Wait 30-60 seconds for data to accumulate
- Check data collector logs for errors

## Next Steps

Once local testing works:
1. ✅ Everything tested locally
2. Commit changes: `git add . && git commit -m "Ready for deployment"`
3. Push to GitHub: `git push`
4. Render will auto-deploy
5. Verify on Render: `https://your-app.onrender.com/health`

