class LifecycleEngine:
    def __init__(self, position: Position):
        self.pos = position

    def process_fill(self, fill: Fill):
        if fill.side.upper() == "BUY":
            self._handle_buy(fill)
        else:
            self._handle_sell(fill)
        
        self.pos.is_open = self.pos.qty != 0

    def _handle_buy(self, fill: Fill):
        # Weighted Average logic
        total_cost = (self.pos.qty * self.pos.avg_price) + (fill.qty * fill.price)
        self.pos.qty += fill.qty
        self.pos.avg_price = total_cost / self.pos.qty if self.pos.qty != 0 else 0

    def _handle_sell(self, fill: Fill):
        # Realized PnL logic: (Sell Price - Entry Price) * Qty
        profit = (fill.price - self.pos.avg_price) * fill.qty
        self.pos.realized_pnl += (profit - fill.fee)
        self.pos.qty -= fill.qty