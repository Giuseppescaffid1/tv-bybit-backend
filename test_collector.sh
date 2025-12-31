#!/bin/bash
# Test script for data collector

echo "🧪 Testing Data Collector..."
echo "================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "1. Testing database connection..."
PYTHONPATH=. python -c "from streamlit.database import init_db, get_session, OrderbookTick; init_db(); session = get_session(); count = session.query(OrderbookTick).count(); print(f'✅ Database connected! Current ticks: {count}')"

echo ""
echo "2. Starting data collector..."
echo "   This will run until you press Ctrl+C"
echo "   Look for: ✅ Saved tick #1 to database"
echo ""

cd streamlit
PYTHONPATH=.. python data_collector.py

