import pandas as pd
import os

class TradeStore:
    def __init__(self, directory="data"):
        self.dir = directory
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

    def log_journal(self, entry: dict):
        # Append-only journal for strategy and emotions
        file_path = f"{self.dir}/journal.csv"
        df = pd.DataFrame([entry])
        df.to_csv(file_path, mode='a', header=not os.path.exists(file_path), index=False)