# ticker.py
import logging
from kiteconnect import KiteTicker

class PriceFeed:
    def __init__(self, api_key, access_token, positions_state):
        self.kws = KiteTicker(api_key, access_token)
        self.state = positions_state  # Shared dict with main app
        self.tokens = []

    def on_ticks(self, ws, ticks):
        for tick in ticks:
            token = tick['instrument_token']
            ltp = tick['last_price']
            
            # Update the LTP in our global state
            if token in self.state:
                pos = self.state[token]
                pos['ltp'] = ltp
                
                # Formula: (LTP - Avg) * Qty
                # For Shorts, it's: (Avg - LTP) * Qty
                multiplier = 1 if pos['qty'] > 0 else -1
                pos['unrealized_pnl'] = (ltp - pos['avg_price']) * pos['qty']
                pos['pnl_percentage'] = ((ltp / pos['avg_price']) - 1) * 100 * multiplier

    def subscribe(self, instrument_tokens):
        self.tokens = instrument_tokens
        self.kws.on_ticks = self.on_ticks
        self.kws.connect(threaded=True)
        self.kws.subscribe(self.tokens)
        self.kws.set_mode(self.kws.MODE_LTP, self.tokens)