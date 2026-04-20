import os, csv
from datetime import datetime

class LifecycleEngine:
    def __init__(self):
        self.positions = {}
        self.closed_trades = []
        self.csv_path = os.path.join(os.getcwd(), "data", "trades.csv")
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Exchange", "Symbol", "Side", "Qty", "Value", "Traded Price", "Closing Price", "PnL", "Type"])

    def log_trade(self, sym, fill, closing_price, pnl, exit_type):
        with open(self.csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "NSE", sym, 
                fill.side, fill.qty, round(fill.value, 2), fill.price, 
                closing_price, round(pnl, 2), exit_type
            ])

    def open_position(self, fill):
        self.positions[fill.symbol] = {
            "qty": fill.qty, "avg_price": fill.price, "side": fill.side,
            "sl": fill.sl, "tp": fill.tp, "value": fill.value, "fill_obj": fill
        }

    def close_position(self, sym, price, exit_type):
        pos = self.positions.pop(sym)
        side_mult = 1 if pos['side'] == "BUY" else -1
        pnl = (price - pos['avg_price']) * pos['qty'] * side_mult
        
        trade = {"symbol": sym, "pnl": round(pnl, 2), "exit_price": price, "exit_time": datetime.now().strftime("%H:%M:%S")}
        self.closed_trades.append(trade)
        self.log_trade(sym, pos['fill_obj'], price, pnl, exit_type)
        return trade