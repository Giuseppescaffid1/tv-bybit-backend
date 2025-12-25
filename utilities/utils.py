from pybit.unified_trading import HTTP

class TradingUtils:
    def __init__(self, api_key: str, api_secret: str):
        self.session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret
        )

    def safe_float(self, val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0  # or raise an error, or return None
    
    def get_wallet_balance(self, account_type: str = "UNIFIED") -> float:
        balance_info = self.session.get_wallet_balance(
            accountType=account_type
        )
        return self.safe_float(balance_info['result']['list'][0]['totalWalletBalance'])
    
    def get_position_info(self, category: str, symbol: str) -> dict:
        positions = self.session.get_positions(
            category=category,
            symbol=symbol,
            openOnly=0,
            limit=1,
        )
        if positions['result']['list']:
            return positions['result']['list'][0]
        entry_price = self.safe_float(positions.get('avgPrice'))
        stop_loss_price = self.safe_float(positions.get('stopLoss'))
        return {
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price
        }

    def compute_qty_risk_based(self):
        wallet_balance = self.get_wallet_balance()
        risk_pct = 0.01
        entry_price = self.get_position_info()['entry_price']
        stop_loss_price = self.get_position_info()['stop_loss_price']
        risk_amount = wallet_balance * risk_pct
        price_distance = abs(entry_price - stop_loss_price)

        if price_distance == 0:
            raise ValueError("Stop loss equals entry price")

        qty = risk_amount / price_distance
        return str(qty)