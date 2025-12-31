"""
Database models and utilities for storing orderbook data
"""
from sqlalchemy import create_engine, Column, Float, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
import pandas as pd

Base = declarative_base()

class OrderbookTick(Base):
    """Model for storing orderbook ticks"""
    __tablename__ = 'orderbook_ticks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    best_bid_price = Column(Float, nullable=False)
    best_bid_size = Column(Float, nullable=False)
    best_ask_price = Column(Float, nullable=False)
    best_ask_size = Column(Float, nullable=False)
    mid_price = Column(Float, nullable=False)
    spread = Column(Float, nullable=False)
    
    def __repr__(self):
        return f"<OrderbookTick(symbol={self.symbol}, ts={self.ts}, price={self.mid_price})>"


def get_database_url():
    """Get database URL from environment or use default"""
    # Render provides DATABASE_URL for PostgreSQL
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        # Render's DATABASE_URL uses postgres:// but SQLAlchemy needs postgresql://
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        return db_url
    else:
        # Fallback for local development
        return 'sqlite:///orderbook.db'


def get_engine():
    """Get SQLAlchemy engine"""
    db_url = get_database_url()
    return create_engine(db_url, echo=False, pool_pre_ping=True)


def get_session():
    """Get database session"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✅ Database tables initialized", flush=True)


def save_tick(tick_data):
    """Save a single tick to database"""
    session = get_session()
    try:
        # Ensure ts is datetime
        if isinstance(tick_data['ts'], str):
            ts = pd.to_datetime(tick_data['ts']).to_pydatetime()
        else:
            ts = tick_data['ts']
        
        tick = OrderbookTick(
            ts=ts,
            symbol=tick_data['symbol'],
            best_bid_price=float(tick_data['best_bid_price']),
            best_bid_size=float(tick_data['best_bid_size']),
            best_ask_price=float(tick_data['best_ask_price']),
            best_ask_size=float(tick_data['best_ask_size']),
            mid_price=float(tick_data.get('mid_price', (tick_data['best_bid_price'] + tick_data['best_ask_price']) / 2)),
            spread=float(tick_data.get('spread', tick_data['best_ask_price'] - tick_data['best_bid_price']))
        )
        session.add(tick)
        session.commit()
    except Exception as e:
        session.rollback()
        import sys
        import traceback
        print(f"❌ Error saving tick: {e}", flush=True, file=sys.stderr)
        traceback.print_exc()
    finally:
        session.close()


def get_latest_ticks(n=2000, symbol='ETHUSDT', minutes_back=10):
    """Get latest ticks from database"""
    session = get_session()
    try:
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_back)
        
        query = session.query(OrderbookTick).filter(
            OrderbookTick.symbol == symbol,
            OrderbookTick.ts >= cutoff_time
        ).order_by(OrderbookTick.ts.desc()).limit(n)
        
        ticks = query.all()
        
        if not ticks:
            # Try to get any recent data (last hour)
            cutoff_time = datetime.utcnow() - timedelta(minutes=60)
            query = session.query(OrderbookTick).filter(
                OrderbookTick.symbol == symbol,
                OrderbookTick.ts >= cutoff_time
            ).order_by(OrderbookTick.ts.desc()).limit(n)
            ticks = query.all()
        
        # Convert to list of dicts
        result = []
        for tick in reversed(ticks):  # Reverse to get chronological order
            result.append({
                'ts': tick.ts.isoformat(),
                'symbol': tick.symbol,
                'best_bid_price': tick.best_bid_price,
                'best_bid_size': tick.best_bid_size,
                'best_ask_price': tick.best_ask_price,
                'best_ask_size': tick.best_ask_size,
                'mid_price': tick.mid_price,
                'spread': tick.spread
            })
        
        return result
    except Exception as e:
        import sys
        print(f"❌ Error getting ticks: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc()
        return []
    finally:
        session.close()


def get_ticks_as_dataframe(n=2000, symbol='ETHUSDT', minutes_back=10):
    """Get latest ticks as pandas DataFrame"""
    try:
        ticks = get_latest_ticks(n=n, symbol=symbol, minutes_back=minutes_back)
        if not ticks:
            return pd.DataFrame()
        
        df = pd.DataFrame(ticks)
        if df.empty:
            return pd.DataFrame()
        
        df['ts'] = pd.to_datetime(df['ts'], utc=True)
        return df
    except Exception as e:
        import sys
        print(f"❌ Error in get_ticks_as_dataframe: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

