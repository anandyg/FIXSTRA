import pandas as pd
import numpy as np
import os

class TradeAnalytics:
    def __init__(self, csv_path="data/journal.csv"):
        self.path = csv_path

    def get_performance(self):
        if not os.path.exists(self.path): return {}
        df = pd.read_csv(self.path)
        if df.empty: return {}

        pnl = df['realized_pnl']
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        
        win_rate = (len(wins) / len(df)) * 100
        # Expectancy: (Win% * AvgWin) - (Loss% * AvgLoss)
        expectancy = (win_rate/100 * wins.mean()) - ((1 - win_rate/100) * abs(losses.mean()))
        
        return {
            "win_rate": f"{win_rate:.1f}%",
            "expectancy": round(expectancy, 2),
            "profit_factor": round(wins.sum() / abs(losses.sum()), 2) if not losses.empty else 0,
            "total_trades": len(df)
        }