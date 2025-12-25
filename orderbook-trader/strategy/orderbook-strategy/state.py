from collections import deque

MAX_POINTS = 500

market_data = deque(maxlen=MAX_POINTS)
trades = []
open_trade = None
