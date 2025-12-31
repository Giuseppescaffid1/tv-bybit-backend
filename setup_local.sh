#!/bin/bash
# Setup script for local testing

echo "🔧 Setting up local testing environment..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# Database Configuration for Local Testing
# This file is gitignored - safe to store credentials here

# External Database URL (use this for local testing from your machine)
DATABASE_URL=postgresql://orderbook_ctoz_user:WSS3XtPCqndwSskDJZN5MvyJCcnWjarx@dpg-d5a7jejuibrs73bmm1mg-a.frankfurt-postgres.render.com:5432/orderbook_ctoz
EOF
    echo "✅ Created .env file"
else
    echo "✅ .env file already exists"
fi

# Check if python-dotenv is installed
echo ""
echo "Checking dependencies..."
python3 -c "import dotenv" 2>/dev/null || {
    echo "Installing python-dotenv..."
    pip install python-dotenv
}

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Test database connection:"
echo "   PYTHONPATH=. python -c \"from streamlit.database import init_db; init_db()\""
echo ""
echo "2. Run data collector (Terminal 1):"
echo "   ./test_collector.sh"
echo "   OR: cd streamlit && PYTHONPATH=.. python data_collector.py"
echo ""
echo "3. Run web app (Terminal 2):"
echo "   ./test_app.sh"
echo "   OR: cd streamlit && PYTHONPATH=.. python app.py"
echo ""
echo "4. Open browser: http://localhost:8050"

