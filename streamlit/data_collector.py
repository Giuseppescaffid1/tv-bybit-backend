"""
Background worker to collect orderbook data from Bybit WebSocket and store in database
This runs as a separate service on Render
"""
import sys
import logging
import time
import threading
from datetime import datetime
import websocket
import json
from collections import deque
from streamlit.database import init_db, save_tick, get_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)


class BybitDataCollector:
    """Collects orderbook data and stores in database"""
    
    def __init__(self, symbol="ETHUSDT", ws_url="wss://stream.bybit.com/v5/public/linear", ping_interval=20):
        self.symbol = symbol
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.ws = None
        self._thread = None
        self._stop = False
        self._ping_thread = None
        self.tick_count = 0
        
    def _send_ping(self, ws):
        """Send ping messages to keep connection alive"""
        while not self._stop:
            time.sleep(self.ping_interval)
            try:
                ws.send(json.dumps({"op": "ping"}))
            except:
                break
    
    def _on_open(self, ws):
        """Handle WebSocket connection opened"""
        logger.info(f"✅ WebSocket connection opened for {self.symbol}")
        print(f"✅ WebSocket connection opened for {self.symbol}", flush=True, file=sys.stderr)
        try:
            sub_msg = {"op": "subscribe", "args": [f"orderbook.1.{self.symbol}"]}
            ws.send(json.dumps(sub_msg))
            logger.info(f"✅ Subscribed to orderbook.1.{self.symbol}")
            print(f"✅ Subscribed to orderbook.1.{self.symbol}", flush=True, file=sys.stderr)
            self._ping_thread = threading.Thread(target=self._send_ping, args=(ws,), daemon=True)
            self._ping_thread.start()
        except Exception as e:
            logger.error(f"❌ Error in _on_open: {e}", exc_info=True)
            print(f"❌ Error in _on_open: {e}", flush=True, file=sys.stderr)
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
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
                
            best_bid_price, best_bid_size = float(bids[0][0]), float(bids[0][1])
            best_ask_price, best_ask_size = float(asks[0][0]), float(asks[0][1])
            
            tick = {
                "ts": datetime.utcnow().isoformat(),
                "symbol": self.symbol,
                "best_bid_price": best_bid_price,
                "best_bid_size": best_bid_size,
                "best_ask_price": best_ask_price,
                "best_ask_size": best_ask_size,
                "mid_price": (best_bid_price + best_ask_price) / 2,
                "spread": best_ask_price - best_bid_price
            }
            
            # Save to database
            try:
                save_tick(tick)
                self.tick_count += 1
                
                # Log every 100 ticks
                if self.tick_count % 100 == 0:
                    logger.info(f"📊 Collected {self.tick_count} ticks. Latest price: {tick['mid_price']:.2f}")
                    print(f"📊 Collected {self.tick_count} ticks. Latest price: {tick['mid_price']:.2f}", flush=True, file=sys.stderr)
                
                # Log first few ticks
                if self.tick_count <= 5:
                    logger.info(f"✅ Saved tick #{self.tick_count} to database: price={tick['mid_price']:.2f}")
                    print(f"✅ Saved tick #{self.tick_count} to database: price={tick['mid_price']:.2f}", flush=True, file=sys.stderr)
            except Exception as e:
                logger.error(f"❌ Error saving tick to database: {e}", exc_info=True)
                print(f"❌ Error saving tick to database: {e}", flush=True, file=sys.stderr)
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}", exc_info=True)
            print(f"❌ Error processing message: {e}", flush=True, file=sys.stderr)
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"❌ WebSocket error: {error}")
        print(f"❌ WebSocket error: {error}", flush=True, file=sys.stderr)
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.warning(f"⚠️ WebSocket closed: {close_status_code}, {close_msg}")
        print(f"⚠️ WebSocket closed: {close_status_code}, {close_msg}", flush=True, file=sys.stderr)
        # Auto-reconnect
        if not self._stop:
            logger.info("🔄 Reconnecting in 5 seconds...")
            time.sleep(5)
            if not self._stop:
                self.start()
    
    def start(self):
        """Start the data collector"""
        self._stop = False
        logger.info(f"🚀 Starting data collector for {self.symbol}...")
        print(f"🚀 Starting data collector for {self.symbol}...", flush=True, file=sys.stderr)
        
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
                    logger.info("🔄 WebSocket thread started")
                    self.ws.run_forever()
                except Exception as e:
                    logger.error(f"❌ WebSocket run_forever error: {e}", exc_info=True)
                    if not self._stop:
                        time.sleep(5)
                        self.start()
            
            self._thread = threading.Thread(target=run_ws, daemon=True)
            self._thread.start()
            logger.info("✅ Data collector started")
            
        except Exception as e:
            logger.error(f"❌ Error starting collector: {e}", exc_info=True)
            if not self._stop:
                threading.Timer(5.0, self.start).start()
    
    def stop(self):
        """Stop the data collector"""
        self._stop = True
        if self.ws:
            self.ws.close()


def main():
    """Main function to run the data collector"""
    logger.info("📦 Starting data collector worker...")
    print("📦 Starting data collector worker...", flush=True, file=sys.stderr)
    
    # Initialize database
    try:
        logger.info("🔧 Initializing database...")
        print("🔧 Initializing database...", flush=True, file=sys.stderr)
        init_db()
        logger.info("✅ Database initialized")
        print("✅ Database initialized", flush=True, file=sys.stderr)
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)
        print(f"❌ Database initialization error: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc()
        # Don't return - try to continue anyway
    
    # Start collector
    logger.info("🚀 Starting Bybit data collector...")
    print("🚀 Starting Bybit data collector...", flush=True, file=sys.stderr)
    collector = BybitDataCollector()
    collector.start()
    
    # Give it a moment to connect
    time.sleep(3)
    
    # Keep the process alive
    try:
        heartbeat_count = 0
        while True:
            time.sleep(60)
            heartbeat_count += 1
            logger.info(f"💓 Heartbeat #{heartbeat_count} - Collected {collector.tick_count} ticks so far")
            print(f"💓 Heartbeat #{heartbeat_count} - Collected {collector.tick_count} ticks so far", flush=True, file=sys.stderr)
            
            # Log database status every 5 minutes
            if heartbeat_count % 5 == 0:
                try:
                    from streamlit.database import get_session, OrderbookTick
                    session = get_session()
                    total_count = session.query(OrderbookTick).count()
                    session.close()
                    logger.info(f"📊 Database status: {total_count} total ticks stored")
                    print(f"📊 Database status: {total_count} total ticks stored", flush=True, file=sys.stderr)
                except Exception as e:
                    logger.error(f"❌ Error checking database: {e}")
    except KeyboardInterrupt:
        logger.info("🛑 Stopping data collector...")
        print("🛑 Stopping data collector...", flush=True, file=sys.stderr)
        collector.stop()


if __name__ == '__main__':
    main()

