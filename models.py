from pydantic import BaseModel
from datetime import datetime

class Fill(BaseModel):
    fill_id: str
    symbol: str
    side: str        # BUY or SELL
    qty: float
    price: float     # Traded Price
    value: float     # Total Value
    sl: float        # Stop Loss Level
    tp: float        # Take Profit Level
    timestamp: datetime = datetime.now()