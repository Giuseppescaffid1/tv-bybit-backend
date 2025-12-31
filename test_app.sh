#!/bin/bash
# Test script for web app

echo "🧪 Testing Web App..."
echo "================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "1. Testing database connection..."
PYTHONPATH=. python -c "from streamlit.database import init_db, get_session, OrderbookTick; init_db(); session = get_session(); count = session.query(OrderbookTick).count(); print(f'✅ Database connected! Current ticks: {count}')"

echo ""
echo "2. Starting web app..."
echo "   Open http://localhost:8050 in your browser"
echo "   Press Ctrl+C to stop"
echo ""

cd streamlit
PYTHONPATH=.. python app.py

