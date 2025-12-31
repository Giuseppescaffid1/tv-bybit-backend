import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit.source import Strategy_A
import sys
import logging

# Configure logging for Render - this will show in logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)
import queue
import threading
from datetime import datetime, timedelta
import websocket
import json
import time
from collections import deque

# ============ WINDOW CONTROL SETTINGS ============
FIXED_WINDOW_MINUTES = 10  # Change this for wider/narrower time window

# Initialize Dash app
app = dash.Dash(__name__)
app.title = "ETHUSDT — Enhanced L1 Liquidity Imbalance Strategy"

# ======================
# BYBIT ORDERBOOK STREAMER CLASS (DEPRECATED - Now using database)
# ======================
# This class is kept for reference but not used - data comes from database via data_collector.py
class BybitOrderbookStreamer:
    def __init__(self, symbol="ETHUSDT", ws_url="wss://stream.bybit.com/v5/public/linear", ping_interval=20, maxlen=3000):
        self.symbol = symbol
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.ws = None
        self.data_queue = queue.Queue(maxsize=1000)
        self._thread = None
        self._stop = False
        self.buffer = deque(maxlen=maxlen)

    def _send_ping(self, ws):
        while not self._stop:
            time.sleep(self.ping_interval)
            try:
                ws.send(json.dumps({"op": "ping"}))
            except:
                break

    def _on_open(self, ws):
        logger.info(f"✅ WebSocket connection opened for {self.symbol}")
        print(f"✅ WebSocket connection opened for {self.symbol}", flush=True, file=sys.stderr)
        try:
            sub_msg = {"op": "subscribe", "args": [f"orderbook.1.{self.symbol}"]}
            ws.send(json.dumps(sub_msg))
            logger.info(f"✅ Subscribed to orderbook.1.{self.symbol}")
            print(f"✅ Subscribed to orderbook.1.{self.symbol}", flush=True, file=sys.stderr)
            threading.Thread(target=self._send_ping, args=(ws,), daemon=True).start()
        except Exception as e:
            logger.error(f"❌ Error in _on_open: {e}", exc_info=True)
            print(f"❌ Error in _on_open: {e}", flush=True, file=sys.stderr)
            import traceback
            traceback.print_exc()

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
            
            # Handle subscription confirmation
            if msg.get("op") == "subscribe" and msg.get("success"):
                logger.info(f"✅ Subscription confirmed: {msg}")
                return
            
            # Handle ping/pong
            if msg.get("op") == "pong":
                return
            
            if "topic" not in msg or not msg["topic"].startswith("orderbook"):
                return
            
            data = msg.get("data", {})
            if not data:
                return
                
            bids = data.get("b", [])
            asks = data.get("a", [])
            if not bids or not asks:
                return
                
            best_bid_price, best_bid_size = bids[0]
            best_ask_price, best_ask_size = asks[0]
            ts = datetime.utcnow().isoformat()
            tick = {
                "ts": ts,
                "symbol": self.symbol,
                "best_bid_price": float(best_bid_price),
                "best_bid_size": float(best_bid_size),
                "best_ask_price": float(best_ask_price),
                "best_ask_size": float(best_ask_size)
            }
            self.buffer.append(tick)
            if not self.data_queue.full():
                self.data_queue.put(tick)
        except Exception as e:
            logger.error(f"❌ Error processing WebSocket message: {e}", exc_info=True)

    def _on_error(self, ws, error):
        logger.error(f"❌ WebSocket error: {error}")
        print(f"❌ WebSocket error: {error}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc()
        # Don't close immediately, let it try to reconnect

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"⚠️ WebSocket closed: {close_status_code}, {close_msg}")
        print(f"⚠️ WebSocket closed: {close_status_code}, {close_msg}", flush=True, file=sys.stderr)
        # Auto-reconnect after a delay
        if not self._stop:
            logger.info("🔄 Attempting to reconnect WebSocket in 5 seconds...")
            print("🔄 Attempting to reconnect WebSocket in 5 seconds...", flush=True, file=sys.stderr)
            time.sleep(5)
            if not self._stop:
                self.start()

    def start(self):
        self._stop = False
        logger.info(f"🚀 Starting WebSocket connection to {self.ws_url}...")
        print(f"🚀 Starting WebSocket connection to {self.ws_url}...", flush=True, file=sys.stderr)
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            def run_ws():
                try:
                    logger.info("🔄 WebSocket thread started, running forever...")
                    print("🔄 WebSocket thread started, running forever...", flush=True, file=sys.stderr)
                    self.ws.run_forever()
                except Exception as e:
                    logger.error(f"❌ WebSocket run_forever error: {e}", exc_info=True)
                    print(f"❌ WebSocket run_forever error: {e}", flush=True, file=sys.stderr)
                    import traceback
                    traceback.print_exc()
                    # Try to reconnect
                    if not self._stop:
                        time.sleep(5)
                        self.start()
            
            self._thread = threading.Thread(target=run_ws, daemon=True)
            self._thread.start()
            logger.info("✅ WebSocket thread started")
            print("✅ WebSocket thread started", flush=True, file=sys.stderr)
        except Exception as e:
            logger.error(f"❌ Error starting WebSocket: {e}", exc_info=True)
            print(f"❌ Error starting WebSocket: {e}", flush=True, file=sys.stderr)
            import traceback
            traceback.print_exc()
            # Retry after delay
            if not self._stop:
                threading.Timer(5.0, self.start).start()

    def stop(self):
        self._stop = True
        if self.ws:
            self.ws.close()

    def get_latest_ticks(self, n=100):
        return list(self.buffer)[-n:] if len(self.buffer) > n else list(self.buffer)

# Initialize database on app startup
try:
    from streamlit.database import init_db
    logger.info("📦 Initializing database connection...")
    print("📦 Initializing database connection...", flush=True, file=sys.stderr)
    init_db()
    logger.info("✅ Database connection initialized")
    print("✅ Database connection initialized", flush=True, file=sys.stderr)
except Exception as e:
    logger.error(f"❌ Database initialization error: {e}", exc_info=True)
    print(f"❌ Database initialization error: {e}", flush=True, file=sys.stderr)

# ======================
# HELPER FUNCTIONS
# ======================
def get_live_df(n=2000):
    """Get live data from database (with lag)"""
    try:
        from streamlit.database import get_ticks_as_dataframe, get_session, OrderbookTick
        from datetime import timedelta
        
        # First check if we have ANY data in the database
        session = get_session()
        try:
            total_count = session.query(OrderbookTick).count()
            logger.info(f"📊 Total ticks in database: {total_count}")
            
            if total_count == 0:
                logger.warning("⚠️ Database is empty - data collector may not be running")
                return pd.DataFrame()
            
            # Get recent data (last 10 minutes)
            df = get_ticks_as_dataframe(n=n, symbol='ETHUSDT', minutes_back=10)
            
            if df.empty:
                # Try getting any recent data (last hour)
                logger.warning("⚠️ No data in last 10 minutes, trying last hour...")
                df = get_ticks_as_dataframe(n=n, symbol='ETHUSDT', minutes_back=60)
                
            if df.empty:
                logger.warning("⚠️ No recent data in database - check data collector worker")
                return pd.DataFrame()
            
            logger.info(f"✅ Retrieved {len(df)} ticks from database (latest: {df['ts'].max()})")
            return df
        finally:
            session.close()
        
    except Exception as e:
        logger.error(f"❌ Error in get_live_df: {e}", exc_info=True)
        print(f"Error in get_live_df: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def filter_fixed_time_window(df, window_minutes=FIXED_WINDOW_MINUTES):
    """Filter the dataframe to only the last window_minutes of data, with at least a fallback number of rows."""
    if df.empty or 'ts' not in df.columns:
        return df
    # Ensure ts column is datetime type
    if not pd.api.types.is_datetime64_any_dtype(df['ts']):
        df['ts'] = pd.to_datetime(df['ts'], errors='coerce', utc=True)
    # Ensure ts column is timezone-aware (UTC)
    if df['ts'].dt.tz is None:
        df['ts'] = df['ts'].dt.tz_localize('UTC')
    elif df['ts'].dt.tz != pd.Timestamp.utcnow().tz:
        df['ts'] = df['ts'].dt.tz_convert('UTC')
    
    # Use timezone-aware timestamp for comparison
    now = pd.Timestamp.utcnow()
    window_start = now - pd.Timedelta(minutes=window_minutes)
    df_window = df[df['ts'] >= window_start]
    if df_window.empty:
        # If by rolling window no data remains, fallback: show last 300 rows
        return df.tail(300)
    return df_window


# ======================
# DASH LAYOUT
# ======================
app.layout = html.Div([
    html.H1("ETHUSDT — Enhanced L1 Liquidity Imbalance Strategy", 
            style={'textAlign': 'center', 'marginBottom': '20px'}),
    
    # Auto-refresh interval (updates every 1 second)
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0, disabled=False),
    
    html.Div([
        # Sidebar parameters
        html.Div([
            html.H3("Parameters", style={'marginTop': '0'}),
            
            html.Details([
                html.Summary("Balance & Fees", style={'fontWeight': 'bold', 'cursor': 'pointer'}),
                html.Div([
                    html.Label("Start balance (USD)", style={'display': 'block', 'marginTop': '10px'}),
                    dcc.Input(id='start_balance', type='number', value=100.0, min=10.0, step=10.0, 
                             style={'width': '100%', 'marginBottom': '10px'}),
                    html.Label("Fee rate per side", style={'display': 'block'}),
                    dcc.Input(id='fee_rate', type='number', value=0.00065, step=0.00001,
                             style={'width': '100%', 'marginBottom': '10px'}),
                ])
            ], open=True, style={'marginBottom': '15px'}),
            
            html.Details([
                html.Summary("Exit Rules", style={'fontWeight': 'bold', 'cursor': 'pointer'}),
                html.Div([
                    html.Label("Take profit %", style={'display': 'block', 'marginTop': '10px'}),
                    dcc.Input(id='tp_pct', type='number', value=0.0025, step=0.0001,
                             style={'width': '100%', 'marginBottom': '10px'}),
                    html.Label("Stop loss %", style={'display': 'block'}),
                    dcc.Input(id='sl_pct', type='number', value=0.0015, step=0.0001,
                             style={'width': '100%', 'marginBottom': '10px'}),
                    dcc.Checklist(id='use_dynamic', 
                                 options=[{'label': 'Use dynamic exits (volatility-based)', 'value': 'yes'}], 
                                 value=['yes'],
                                 style={'marginBottom': '10px'}),
                    html.Label("Volatility window", style={'display': 'block'}),
                    dcc.Slider(id='vol_window', min=20, max=100, value=50, 
                              marks={i: str(i) for i in range(20, 101, 20)},
                              tooltip={"placement": "bottom", "always_visible": True}),
                ])
            ], open=True, style={'marginBottom': '15px'}),
            
            html.Details([
                html.Summary("Signal Logic", style={'fontWeight': 'bold', 'cursor': 'pointer'}),
                html.Div([
                    html.Label("Imbalance smoothing window", style={'display': 'block', 'marginTop': '10px'}),
                    dcc.Slider(id='window', min=5, max=50, value=15, 
                              marks={i: str(i) for i in range(5, 51, 10)},
                              tooltip={"placement": "bottom", "always_visible": True}),
                    html.Label("Long threshold", style={'display': 'block', 'marginTop': '10px'}),
                    dcc.Slider(id='long_th', min=0.05, max=0.40, value=0.15, step=0.01,
                              marks={0.15: '0.15', 0.30: '0.30'},
                              tooltip={"placement": "bottom", "always_visible": True}),
                    html.Label("Short threshold", style={'display': 'block', 'marginTop': '10px'}),
                    dcc.Slider(id='short_th', min=-0.40, max=-0.05, value=-0.15, step=0.01,
                              marks={-0.15: '-0.15', -0.30: '-0.30'},
                              tooltip={"placement": "bottom", "always_visible": True}),
                    html.Label("Min signal duration (ticks)", style={'display': 'block', 'marginTop': '10px'}),
                    dcc.Slider(id='min_duration', min=1, max=10, value=3,
                              marks={i: str(i) for i in range(1, 11, 2)},
                              tooltip={"placement": "bottom", "always_visible": True}),
                ])
            ], open=True, style={'marginBottom': '15px'}),
            
            html.Details([
                html.Summary("Risk & Filters", style={'fontWeight': 'bold', 'cursor': 'pointer'}),
                html.Div([
                    html.Label("Risk per trade % of equity", style={'display': 'block', 'marginTop': '10px'}),
                    dcc.Input(id='risk_pct', type='number', value=0.015, step=0.001,
                             style={'width': '100%', 'marginBottom': '10px'}),
                    html.Label("Max spread (USDT)", style={'display': 'block'}),
                    dcc.Slider(id='max_spread', min=0.01, max=0.50, value=0.08, step=0.01,
                              marks={0.08: '0.08', 0.20: '0.20', 0.40: '0.40'},
                              tooltip={"placement": "bottom", "always_visible": True}),
                ])
            ], open=True),
            
        ], style={'width': '20%', 'float': 'left', 'padding': '20px', 'backgroundColor': '#f8f9fa', 
                 'height': '100vh', 'overflowY': 'auto', 'borderRight': '1px solid #ddd'}),
        
        # Main content area
        html.Div([
            # Status indicator
            html.Div(id='status-indicator', 
                    style={'padding': '10px', 'marginBottom': '10px', 'backgroundColor': '#e9ecef', 
                           'borderRadius': '5px', 'fontWeight': 'bold'}),
            
            # System Guide
            html.Details([
                html.Summary("📖 System Guide - How to Use This Dashboard", 
                           style={'fontWeight': 'bold', 'fontSize': '18px', 'cursor': 'pointer', 
                                 'padding': '10px', 'backgroundColor': '#007bff', 'color': 'white',
                                 'borderRadius': '5px', 'marginBottom': '10px'}),
                html.Div([
                    html.H4("🎯 Strategy Overview", style={'color': '#007bff', 'marginTop': '15px'}),
                    html.P([
                        "This system uses ", html.Strong("Level 1 (L1) Orderbook Imbalance"), " to identify potential price movements. ",
                        "The strategy looks for strong imbalances between bid and ask sizes, combined with price momentum signals."
                    ], style={'lineHeight': '1.6'}),
                    
                    html.H4("📊 Understanding the Charts", style={'color': '#007bff', 'marginTop': '20px'}),
                    html.Ul([
                        html.Li([
                            html.Strong("Price Chart (Top Panel):"),
                            " Shows the mid-price with entry/exit markers. ",
                            html.Span("Green circles", style={'color': '#2ca02c', 'fontWeight': 'bold'}), " = Entry points, ",
                            html.Span("Red X", style={'color': '#d62728', 'fontWeight': 'bold'}), " = Exit points. ",
                            "Green lines = profitable trades, Red lines = losing trades."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("L1 Imbalance (Middle Panel):"),
                            " Shows the smoothed imbalance ratio. ",
                            html.Span("Positive values", style={'color': '#2ca02c', 'fontWeight': 'bold'}), 
                            " (above 0) indicate more buy pressure, ",
                            html.Span("negative values", style={'color': '#d62728', 'fontWeight': 'bold'}), 
                            " indicate more sell pressure. ",
                            "The horizontal lines show the entry thresholds."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Spread (Bottom Panel):"),
                            " Shows the bid-ask spread. Lower spreads indicate better liquidity. ",
                            "Trades only execute when spread is below the maximum threshold."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Equity Curve:"),
                            " Shows your account balance over time. ",
                            "The dashed line indicates your starting balance."
                        ], style={'marginBottom': '10px'}),
                    ]),
                    
                    html.H4("🔍 What to Look For", style={'color': '#007bff', 'marginTop': '20px'}),
                    html.Ul([
                        html.Li([
                            html.Strong("Strong Imbalance Signals:"),
                            " Look for imbalance values that exceed the thresholds (",
                            html.Span("> 0.15 for longs", style={'color': '#2ca02c'}), " or ",
                            html.Span("< -0.15 for shorts", style={'color': '#d62728'}), 
                            ") and persist for several ticks."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Price Momentum:"),
                            " The system looks for price 'minibursts' (sudden movements) or local extrema ",
                            "(price turning points) that align with the imbalance direction."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Entry Conditions:"),
                            " A trade opens when: (1) Strong imbalance persists, (2) Price momentum confirms, ",
                            "(3) Spread is acceptable, (4) Micro-price bias aligns with direction."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Exit Conditions:"),
                            " Trades close at Take Profit (TP) or Stop Loss (SL) levels, ",
                            "which are dynamically adjusted based on volatility."
                        ], style={'marginBottom': '10px'}),
                    ]),
                    
                    html.H4("⚙️ Key Parameters", style={'color': '#007bff', 'marginTop': '20px'}),
                    html.Ul([
                        html.Li([
                            html.Strong("Long/Short Threshold:"),
                            " Minimum imbalance strength required to trigger a signal. Higher = more selective."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Min Signal Duration:"),
                            " How many consecutive ticks the signal must persist before opening a trade."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Risk per Trade:"),
                            " Percentage of equity risked on each trade (position sizing)."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Dynamic Exits:"),
                            " When enabled, TP/SL adjust based on market volatility."
                        ], style={'marginBottom': '10px'}),
                    ]),
                    
                    html.H4("📈 Reading the Stats", style={'color': '#007bff', 'marginTop': '20px'}),
                    html.Ul([
                        html.Li([
                            html.Strong("Win Rate:"),
                            " Percentage of profitable trades. Aim for > 50%."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Profit Factor:"),
                            " Ratio of gross profit to gross loss. Values > 1.5 are good."
                        ], style={'marginBottom': '10px'}),
                        html.Li([
                            html.Strong("Max Drawdown:"),
                            " Largest peak-to-trough decline. Monitor to assess risk."
                        ], style={'marginBottom': '10px'}),
                    ]),
                    
                    html.Div([
                        html.P([
                            html.Strong("💡 Tip: "),
                            "Watch for clusters of successful trades (green lines) in similar market conditions. ",
                            "This helps identify when the strategy performs best."
                        ], style={'padding': '15px', 'backgroundColor': '#fff3cd', 'borderRadius': '5px', 
                                 'borderLeft': '4px solid #ffc107', 'marginTop': '20px'})
                    ]),
                ], style={'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px', 
                         'marginBottom': '20px', 'lineHeight': '1.6'})
            ], open=False, style={'marginBottom': '20px'}),
            
            # Main chart
            dcc.Graph(id='main-chart', style={'marginBottom': '20px'}),
            
            # Stats row
            html.Div(id='stats-row', 
                    style={'display': 'grid', 'gridTemplateColumns': 'repeat(5, 1fr)', 
                           'gap': '10px', 'marginBottom': '20px'}),
            
            # Equity curve
            dcc.Graph(id='equity-chart', style={'marginBottom': '20px'}),
            
            # Live orderbook
            html.Div([
                html.H3("Live Orderbook Feed (Bybit WS)"),
                html.Div(id='orderbook-table', style={'marginBottom': '20px'}),
                dcc.Graph(id='orderbook-chart')
            ], style={'marginTop': '20px'}),
            
            # Trade log
            html.Details([
                html.Summary("Trade Log", style={'fontWeight': 'bold', 'fontSize': '18px', 'cursor': 'pointer'}),
                html.Div(id='trade-log')
            ], style={'marginTop': '20px'}),
            
        ], style={'width': '78%', 'float': 'right', 'padding': '20px'}),
        
    ], style={'display': 'flex'}),
    
], style={'fontFamily': 'Arial, sans-serif'})

# Add CSS and JavaScript to prevent auto-scroll on updates
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Prevent auto-scroll and focus jumping */
            html, body {
                scroll-behavior: auto !important;
            }
            .dash-graph {
                outline: none !important;
                min-height: 300px; /* Prevent height collapse */
                height: auto !important;
            }
            /* Prevent graph containers from causing scroll jumps */
            .js-plotly-plot {
                contain: layout style paint;
                min-height: 300px;
            }
            /* Fix graph container heights to prevent layout shifts */
            #main-chart {
                height: 900px !important;
                min-height: 900px !important;
            }
            #equity-chart {
                height: 300px !important;
                min-height: 300px !important;
            }
            #orderbook-chart {
                height: 300px !important;
                min-height: 300px !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        <script>
            (function() {
                let savedScrollPosition = 0;
                let isUserScrolling = false;
                
                // Save scroll position
                function saveScrollPosition() {
                    savedScrollPosition = window.pageYOffset || document.documentElement.scrollTop;
                }
                
                // Restore scroll position
                function restoreScrollPosition() {
                    if (!isUserScrolling && savedScrollPosition > 0) {
                        window.scrollTo(0, savedScrollPosition);
                    }
                }
                
                // Track user scrolling
                let scrollTimeout;
                window.addEventListener('scroll', function() {
                    isUserScrolling = true;
                    saveScrollPosition();
                    clearTimeout(scrollTimeout);
                    scrollTimeout = setTimeout(function() {
                        isUserScrolling = false;
                    }, 150);
                });
                
                // Save scroll before Dash updates
                document.addEventListener('DOMContentLoaded', function() {
                    saveScrollPosition();
                    
                    // Monitor for Dash updates and restore scroll
                    const observer = new MutationObserver(function() {
                        if (!isUserScrolling) {
                            setTimeout(restoreScrollPosition, 10);
                        }
                    });
                    
                    observer.observe(document.body, {
                        childList: true,
                        subtree: true
                    });
                });
            })();
        </script>
    </body>
</html>
'''

# ======================
# CALLBACKS
# ======================
@app.callback(
    [Output('main-chart', 'figure'),
     Output('equity-chart', 'figure'),
     Output('stats-row', 'children'),
     Output('orderbook-table', 'children'),
     Output('orderbook-chart', 'figure'),
     Output('trade-log', 'children'),
     Output('status-indicator', 'children')],
    [Input('interval-component', 'n_intervals')],
    [State('start_balance', 'value'),
     State('fee_rate', 'value'),
     State('tp_pct', 'value'),
     State('sl_pct', 'value'),
     State('use_dynamic', 'value'),
     State('vol_window', 'value'),
     State('window', 'value'),
     State('long_th', 'value'),
     State('short_th', 'value'),
     State('min_duration', 'value'),
     State('risk_pct', 'value'),
     State('max_spread', 'value')]
)
def update_dashboard(n, start_balance, fee_rate, tp_pct, sl_pct, use_dynamic, vol_window, 
                     window, long_th, short_th, min_duration, risk_pct, max_spread):
    # Wrap entire callback in try-except for safety
    try:
        # Get live data
        try:
            live_df = get_live_df(n=2000)
            if live_df is None or live_df.empty:
                # Check database status
                try:
                    from streamlit.database import get_session, OrderbookTick
                    session = get_session()
                    total_count = session.query(OrderbookTick).count()
                    session.close()
                    
                    if total_count == 0:
                        message = "⏳ Database is empty. Waiting for data collector to start collecting data..."
                    else:
                        message = f"⏳ No recent data (last 10 min). Database has {total_count} total ticks. Check data collector worker."
                except Exception as e:
                    message = f"⏳ Waiting for live data... (DB error: {str(e)[:50]})"
                
                empty_fig = go.Figure()
                empty_fig.add_annotation(text="No live data available", 
                                        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                                        font=dict(size=20))
                empty_fig.update_layout(template="plotly_white", height=400)
                return (empty_fig, empty_fig, html.Div("Waiting..."), 
                        html.Div("Waiting..."), empty_fig, html.Div(""), 
                        html.Div(message, style={'color': 'orange'}))
        except Exception as e:
            empty_fig = go.Figure()
            empty_fig.add_annotation(text=f"Error getting live data: {str(e)}", 
                                    xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            empty_fig.update_layout(template="plotly_white", height=400)
            return (empty_fig, empty_fig, html.Div("Error"), 
                    html.Div("Error"), empty_fig, html.Div(""), 
                    html.Div(f"❌ Error getting data: {str(e)}", style={'color': 'red'}))

        # ---- Fixed window logic ----
        window_minutes = FIXED_WINDOW_MINUTES
        view = filter_fixed_time_window(live_df, window_minutes=window_minutes)
        if view.empty or len(view) < 10:
            empty_fig = go.Figure()
            empty_fig.add_annotation(text=f"Waiting for at least 10 data points in last {window_minutes} min...", 
                                    xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                                    font=dict(size=20))
            empty_fig.update_layout(template="plotly_white", height=400)
            return (empty_fig, empty_fig, html.Div("Waiting..."), 
                    html.Div("Waiting..."), empty_fig, html.Div(""), 
                    html.Div("⏳ Waiting for data...", style={'color': 'orange'}))
        
        # Run strategy on the underlying full dataframe, so trade/equity calculation is not visually dependent
        use_dynamic_bool = 'yes' in use_dynamic if use_dynamic else False
        try:
            strat = Strategy_A(
                df=live_df,
                start_balance=start_balance,
                fee_rate=fee_rate,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                window=window,
                long_th=long_th,
                short_th=short_th,
                max_spread=max_spread,
                risk_pct=risk_pct,
                min_imb_duration=min_duration,
                use_dynamic_exits=use_dynamic_bool,
                volatility_window=vol_window
            )
            df, trades = strat.backtest()
        except Exception as e:
            empty_fig = go.Figure()
            empty_fig.add_annotation(text=f"Error: {str(e)}", 
                                    xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            empty_fig.update_layout(template="plotly_white", height=400)
            return (empty_fig, empty_fig, html.Div("Error"), 
                    html.Div("Error"), empty_fig, html.Div(""), 
                    html.Div(f"❌ Error: {str(e)}", style={'color': 'red'}))

        if df.empty:
            empty_fig = go.Figure()
            return (empty_fig, empty_fig, html.Div("No data"), 
                    html.Div("No data"), empty_fig, html.Div(""), 
                    html.Div("❌ No data", style={'color': 'red'}))
        
        # Ensure visualization (main graph) uses only fixed time window:
        if 'ts' not in df.columns:
            empty_fig = go.Figure()
            empty_fig.add_annotation(text="Missing timestamp column", 
                                    xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            empty_fig.update_layout(template="plotly_white", height=400)
            return (empty_fig, empty_fig, html.Div("Error"), 
                    html.Div("Error"), empty_fig, html.Div(""), 
                    html.Div("❌ Missing timestamp column", style={'color': 'red'}))
        
        # Ensure ts column is datetime type and timezone-aware (UTC)
        if not pd.api.types.is_datetime64_any_dtype(df['ts']):
            df['ts'] = pd.to_datetime(df['ts'], errors='coerce', utc=True)
        # Ensure timezone-aware
        if df['ts'].dt.tz is None:
            df['ts'] = df['ts'].dt.tz_localize('UTC')
        elif df['ts'].dt.tz != pd.Timestamp.utcnow().tz:
            df['ts'] = df['ts'].dt.tz_convert('UTC')
        
        # Use timezone-aware timestamp for comparison
        window_start = pd.Timestamp.utcnow() - pd.Timedelta(minutes=window_minutes)
        view = df[df['ts'] >= window_start]
        if view.empty:
            view = df.tail(300)
        
        if view.empty:
            empty_fig = go.Figure()
            return (empty_fig, empty_fig, html.Div("No view data"), 
                    html.Div("No view data"), empty_fig, html.Div(""), 
                    html.Div("❌ No view data", style={'color': 'red'}))

        # Get only recent trades and those visible on the current window
        end_ts = view["ts"].iloc[-1]
        min_ts = view["ts"].iloc[0]
        trades_view = pd.DataFrame()
        if not trades.empty and "ts_entry" in trades.columns and "ts_exit" in trades.columns:
            try:
                # Ensure trade timestamps are datetime type and timezone-aware (UTC)
                trades_copy = trades.copy()
                if not pd.api.types.is_datetime64_any_dtype(trades_copy["ts_entry"]):
                    trades_copy["ts_entry"] = pd.to_datetime(trades_copy["ts_entry"], errors='coerce', utc=True)
                if not pd.api.types.is_datetime64_any_dtype(trades_copy["ts_exit"]):
                    trades_copy["ts_exit"] = pd.to_datetime(trades_copy["ts_exit"], errors='coerce', utc=True)
                
                # Ensure timezone-aware
                if trades_copy["ts_entry"].dt.tz is None:
                    trades_copy["ts_entry"] = trades_copy["ts_entry"].dt.tz_localize('UTC')
                if trades_copy["ts_exit"].dt.tz is None:
                    trades_copy["ts_exit"] = trades_copy["ts_exit"].dt.tz_localize('UTC')
                
                trades_view = trades_copy[
                    (trades_copy["ts_exit"] <= end_ts) & (trades_copy["ts_entry"] >= min_ts)
                ]
            except Exception:
                trades_view = pd.DataFrame()
        
        # Main chart
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            row_heights=[0.55, 0.20, 0.25],
            vertical_spacing=0.02,
            subplot_titles=(f"Price with TP/SL (Last {window_minutes} min)", "L1 Imbalance", "Spread")
        )
        
        # Price line
        if 'mid_price' in view.columns and not view['mid_price'].isna().all():
            fig.add_trace(
                go.Scatter(x=view["ts"], y=view["mid_price"], mode="lines", name="Mid Price",
                          line=dict(width=1.5, color="#1f77b4"), hovertemplate="Time: %{x}<br>Price: %{y:.2f}<extra></extra>"),
                row=1, col=1
            )
        
        # Trade markers
        if not trades_view.empty:
            fig.add_trace(
                go.Scatter(x=trades_view["ts_entry"], y=trades_view["entry"], mode="markers",
                          name="Entry", marker=dict(size=10, symbol="circle", color="#222", 
                                                   line=dict(width=1, color="#fff")),
                          text=trades_view["side"], hovertemplate="Entry<br>Side: %{text}<br>Price: %{y:.2f}<extra></extra>"),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=trades_view["ts_exit"], y=trades_view["exit"], mode="markers",
                          name="Exit", marker=dict(size=10, symbol="x", color="#d62728",
                                                  line=dict(width=1, color="#fff")),
                          text=trades_view["reason"], hovertemplate="Exit<br>Reason: %{text}<br>Price: %{y:.2f}<extra></extra>"),
                row=1, col=1
            )
            
            # TP/SL lines
            for _, t in trades_view.iterrows():
                color = "#2ca02c" if t["net_pnl_usd"] > 0 else "#d62728"
                fig.add_trace(
                    go.Scatter(x=[t["ts_entry"], t["ts_exit"]], y=[t["entry"], t["exit"]],
                              mode="lines", line=dict(width=2, color=color), showlegend=False, hoverinfo="skip"),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(x=[t["ts_entry"], t["ts_exit"]], y=[t["tp_price"], t["tp_price"]],
                              mode="lines", line=dict(width=1, color="#98df8a", dash="dot"), 
                              showlegend=False, hovertemplate=f"TP: {t['tp_price']:.2f}<extra></extra>"),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(x=[t["ts_entry"], t["ts_exit"]], y=[t["sl_price"], t["sl_price"]],
                              mode="lines", line=dict(width=1, color="#ff9896", dash="dot"), 
                              showlegend=False, hovertemplate=f"SL: {t['sl_price']:.2f}<extra></extra>"),
                    row=1, col=1
                )
        
        # Imbalance panel
        if "l1_imb_smooth" in view.columns:
            fig.add_trace(
                go.Scatter(x=view["ts"], y=view["l1_imb_smooth"], mode="lines", name="L1 Imbalance (smooth)",
                      line=dict(width=1.2, color="#9467bd"), hovertemplate="Time: %{x}<br>Imbalance: %{y:.3f}<extra></extra>"),
                row=2, col=1
            )
            fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray", row=2, col=1)
            fig.add_hline(y=long_th, line_width=1, line_dash="dot", line_color="#2ca02c", row=2, col=1)
            fig.add_hline(y=short_th, line_width=1, line_dash="dot", line_color="#d62728", row=2, col=1)
        
        # Spread panel
        if "spread" in view.columns:
            fig.add_trace(
                go.Scatter(x=view["ts"], y=view["spread"], mode="lines", name="Spread",
                      line=dict(width=1, color="#ff7f0e"), fill='tozeroy',
                      hovertemplate="Time: %{x}<br>Spread: %{y:.4f}<extra></extra>"),
                row=3, col=1
            )
            fig.add_hline(y=max_spread, line_width=1, line_dash="dot", line_color="#d62728", row=3, col=1)
        
        # Calculate stable Y-axis ranges to prevent jumping
        price_range = None
        imbalance_range = None
        spread_range = None
        
        if 'mid_price' in view.columns and not view['mid_price'].isna().all():
            price_min = view['mid_price'].min()
            price_max = view['mid_price'].max()
            price_padding = (price_max - price_min) * 0.1  # 10% padding
            price_range = [price_min - price_padding, price_max + price_padding]
        
        if 'l1_imb_smooth' in view.columns and not view['l1_imb_smooth'].isna().all():
            imb_min = view['l1_imb_smooth'].min()
            imb_max = view['l1_imb_smooth'].max()
            imb_padding = (imb_max - imb_min) * 0.1 if (imb_max - imb_min) > 0 else 0.1
            imbalance_range = [imb_min - imb_padding, imb_max + imb_padding]
        else:
            imbalance_range = [-1, 1]  # Default range for imbalance
        
        if 'spread' in view.columns and not view['spread'].isna().all():
            spread_min = view['spread'].min()
            spread_max = view['spread'].max()
            spread_padding = (spread_max - spread_min) * 0.1 if (spread_max - spread_min) > 0 else 0.001
            spread_range = [max(0, spread_min - spread_padding), spread_max + spread_padding]
        
        fig.update_layout(
            hovermode="x unified",
            template="plotly_white",
            height=900, 
            margin=dict(l=20, r=20, t=40, b=20),
            uirevision='main-chart',  # Preserves zoom/pan state on updates
        )

        # Fixed window x-range:
        if not view.empty and 'ts' in view.columns:
            try:
                x0, x1 = view["ts"].iloc[0], view["ts"].iloc[-1]
                fig.update_xaxes(
                    range=[x0, x1],
                    autorange=False,
                    rangeslider=dict(visible=True),
                    row=3, col=1
                )
            except Exception:
                pass  # Use default range if there's an issue
        
        # Set stable Y-axis ranges to prevent vertical expansion
        if price_range:
            fig.update_yaxes(
                title_text="Price (USDT)", 
                range=price_range,
                autorange=False,
                fixedrange=False,  # Allow user zoom but prevent auto-resize
                row=1, col=1
            )
        else:
            fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
        
        if imbalance_range:
            fig.update_yaxes(
                title_text="Imbalance", 
                range=imbalance_range,
                autorange=False,
                fixedrange=False,
                row=2, col=1
            )
        else:
            fig.update_yaxes(title_text="Imbalance", row=2, col=1)
        
        if spread_range:
            fig.update_yaxes(
                title_text="Spread (USDT)", 
                range=spread_range,
                autorange=False,
                fixedrange=False,
                row=3, col=1
            )
        else:
            fig.update_yaxes(title_text="Spread (USDT)", row=3, col=1)
        
        # Equity chart (full range for equity, not just last X min)
        fig_eq = go.Figure()
        if not trades.empty and "ts_exit" in trades.columns and "equity_curve" in trades.columns:
            fig_eq.add_trace(
                go.Scatter(x=trades["ts_exit"], y=trades["equity_curve"],
                          mode="lines+markers", name="Equity", line=dict(width=2, color="#1f77b4"), fill='tozeroy',
                          hovertemplate="Time: %{x}<br>Equity: %{y:.2f}<extra></extra>")
            )
        fig_eq.add_hline(y=start_balance, line_dash="dash", line_color="gray", annotation_text="Start")
        
        # Calculate stable equity range to prevent vertical expansion
        equity_range = None
        if not trades.empty and "equity_curve" in trades.columns:
            equity_min = float(trades["equity_curve"].min())
            equity_max = float(trades["equity_curve"].max())
            if equity_max > equity_min:
                equity_padding = (equity_max - equity_min) * 0.1
                equity_range = [max(0, equity_min - equity_padding), equity_max + equity_padding]
            else:
                equity_range = [start_balance * 0.9, start_balance * 1.1]
        
        fig_eq.update_layout(template="plotly_white", hovermode="x unified", height=300, 
                            margin=dict(l=20, r=20, t=30, b=20),
                            uirevision='equity-chart')  # Preserves zoom/pan state on updates
        
        if equity_range:
            fig_eq.update_yaxes(title_text="Equity (USD)", range=equity_range, autorange=False, fixedrange=False)
        else:
            fig_eq.update_yaxes(title_text="Equity (USD)", autorange=True)
        
        # Stats
        stats = Strategy_A.compute_stats(trades, start_balance) if not trades.empty else {}
        stats_children = []
        if stats:
            stats_children = [
            html.Div([
                html.H4("Trades", style={'margin': '0', 'color': '#666'}),
                html.P(str(stats.get("Trades", 0)), style={'fontSize': '24px', 'fontWeight': 'bold', 'margin': '5px 0'})
            ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
            html.Div([
                html.H4("Win Rate", style={'margin': '0', 'color': '#666'}),
                html.P(f'{stats.get("Win rate", 0)*100:.1f}%', 
                      style={'fontSize': '24px', 'fontWeight': 'bold', 'margin': '5px 0',
                            'color': '#2ca02c' if stats.get("Win rate", 0) > 0.5 else '#d62728'})
            ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
            html.Div([
                html.H4("Profit Factor", style={'margin': '0', 'color': '#666'}),
                html.P("∞" if stats.get("Profit factor", 0) == float("inf") else f"{stats.get('Profit factor', 0):.2f}",
                      style={'fontSize': '24px', 'fontWeight': 'bold', 'margin': '5px 0'})
            ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
            html.Div([
                html.H4("Total PnL", style={'margin': '0', 'color': '#666'}),
                html.P(f'${stats.get("Total net PnL (USD)", 0):.2f}',
                      style={'fontSize': '24px', 'fontWeight': 'bold', 'margin': '5px 0',
                            'color': '#2ca02c' if stats.get("Total net PnL (USD)", 0) > 0 else '#d62728'})
            ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
            html.Div([
                html.H4("ROI", style={'margin': '0', 'color': '#666'}),
                html.P(f'{stats.get("ROI", 0)*100:.1f}%',
                      style={'fontSize': '24px', 'fontWeight': 'bold', 'margin': '5px 0',
                            'color': '#2ca02c' if stats.get("ROI", 0) > 0 else '#d62728'})
            ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
            ]
        
        # Orderbook table - get from database
        try:
            from streamlit.database import get_latest_ticks
            latest_ticks = get_latest_ticks(n=20, symbol='ETHUSDT', minutes_back=10)
        except Exception as e:
            logger.error(f"❌ Error getting latest ticks: {e}")
            latest_ticks = []
        if latest_ticks:
            try:
                df_live = pd.DataFrame(latest_ticks)
                if not df_live.empty and 'ts' in df_live.columns:
                    # Convert ts to datetime if it's a string
                    if df_live['ts'].dtype == 'object':
                        df_live['ts'] = pd.to_datetime(df_live['ts'], errors='coerce')
                    
                    table = html.Div([
                        html.Table([
                            html.Thead(html.Tr([html.Th(col, style={'padding': '8px', 'border': '1px solid #ddd'}) 
                                                for col in df_live.columns])),
                            html.Tbody([html.Tr([html.Td(str(df_live.iloc[i][col]), style={'padding': '8px', 'border': '1px solid #ddd'}) 
                                                for col in df_live.columns]) 
                                                for i in range(len(df_live))])
                        ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '12px'})
                    ], style={'overflowX': 'auto'})
                    
                    # Orderbook chart
                    fig_ob = go.Figure()
                    if 'best_bid_price' in df_live.columns and 'best_ask_price' in df_live.columns:
                        fig_ob.add_trace(go.Scatter(x=df_live['ts'], y=df_live['best_bid_price'], name='Bid', 
                                                   line=dict(color='green', width=2)))
                        fig_ob.add_trace(go.Scatter(x=df_live['ts'], y=df_live['best_ask_price'], name='Ask', 
                                                   line=dict(color='red', width=2)))
                    fig_ob.update_layout(template="plotly_white", height=300, hovermode="x unified",
                                        title="Live Bid/Ask Prices",
                                        uirevision='orderbook-chart')  # Preserves zoom/pan state
                else:
                    table = html.Div("Waiting for data...", style={'padding': '20px', 'textAlign': 'center'})
                    fig_ob = go.Figure()
                    fig_ob.update_layout(template="plotly_white", height=300)
            except Exception as e:
                table = html.Div(f"Error loading orderbook: {str(e)}", style={'padding': '20px', 'textAlign': 'center', 'color': 'red'})
                fig_ob = go.Figure()
                fig_ob.update_layout(template="plotly_white", height=300)
        else:
            table = html.Div("Waiting for data...", style={'padding': '20px', 'textAlign': 'center'})
            fig_ob = go.Figure()
            fig_ob.update_layout(template="plotly_white", height=300)
        
        # Trade log
        if not trades_view.empty:
            display_cols = ["trade_id", "side", "ts_entry", "entry", "tp_price", "sl_price",
                            "ts_exit", "exit", "qty", "reason", "gross_pnl_usd", "fees_usd", 
                            "net_pnl_usd", "equity_curve"]
            available_cols = [col for col in display_cols if col in trades_view.columns]
            
            trade_log = html.Div([
            html.Table([
                html.Thead(html.Tr([html.Th(col, style={'padding': '8px', 'border': '1px solid #ddd', 
                                                       'backgroundColor': '#f8f9fa'}) 
                                   for col in available_cols])),
                html.Tbody([html.Tr([html.Td(f"{trades_view.iloc[i][col]:.4f}" if isinstance(trades_view.iloc[i][col], float) else str(trades_view.iloc[i][col]),
                                           style={'padding': '8px', 'border': '1px solid #ddd',
                                                 'color': '#2ca02c' if col == 'net_pnl_usd' and trades_view.iloc[i][col] > 0 else 
                                                         '#d62728' if col == 'net_pnl_usd' and trades_view.iloc[i][col] < 0 else 'black'}) 
                                   for col in available_cols]) 
                                   for i in range(len(trades_view))])
            ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '11px'})
            ], style={'overflowX': 'auto', 'maxHeight': '400px', 'overflowY': 'auto'})
        else:
            trade_log = html.Div("No trades yet.", style={'padding': '20px', 'textAlign': 'center'})
    
        try:
            live_df_len = len(live_df) if live_df is not None and not live_df.empty else 0
        except Exception:
            live_df_len = 0
        
        status = html.Div([
            html.Span("✅ Live", style={'color': 'green', 'fontWeight': 'bold'}),
            html.Span(f" | {live_df_len} ticks", style={'marginLeft': '10px'}),
            html.Span(f" | Last update: {datetime.now().strftime('%H:%M:%S')}", style={'marginLeft': '10px', 'color': '#666'}),
            html.Span(f" | Showing last {window_minutes} min window", style={'marginLeft': '10px', 'color': '#0066aa'})
        ])
        
        return fig, fig_eq, stats_children, table, fig_ob, trade_log, status
    
    except Exception as e:
        # Catch any unexpected errors and return error state
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"Callback error: {error_msg}\n{traceback_str}")
        
        empty_fig = go.Figure()
        empty_fig.add_annotation(text=f"Unexpected error: {error_msg}", 
                                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                                font=dict(size=16))
        empty_fig.update_layout(template="plotly_white", height=400)
        
        return (empty_fig, empty_fig, html.Div("Error"), 
                html.Div("Error"), empty_fig, html.Div(""), 
                html.Div(f"❌ Unexpected error: {error_msg}", style={'color': 'red'}))

# Make server accessible for gunicorn
server = app.server

if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=8050)