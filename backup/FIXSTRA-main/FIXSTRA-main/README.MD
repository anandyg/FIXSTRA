# FIXSTRA | Pro Algorithmic Trading Desk

FIXSTRA is a high-performance, real-time algorithmic trading dashboard built with **FastAPI** and **WebSockets**. It is designed for paper trading both Indian Equity (via Zerodha Kite) and Crypto markets (via Binance), featuring a professional high-contrast UI and automated strategy execution.

## 🚀 Key Features

* **Real-Time Market Watch**: 1-second refresh grid with daily percentage change and color-coded volatility.
* **Dual Mode Connectivity**: Seamlessly switch between Crypto (Binance WebSocket) and Indian Markets (Kite Ticker).
* **Automated Strategy Engine**: Implements a high-precision EMA 5/20 crossover strategy on a 1-minute closing basis.
* **Telegram Integration**: Instant alerts for system startup, new trade entries, and profit/loss exits.
* **Live Portfolio Tracking**: Real-time calculation of Total Investment, Current Value, and Combined P&L.

---

## 📈 Strategy: EMA 5/20 Closing Basis

The engine utilizes an Exponential Moving Average (EMA) crossover logic optimized for 1-minute intervals:

* **BUY Signal**: Triggered when the **EMA 5** crosses above the **EMA 20** AND the 1-minute candle closes strictly above both averages.
* **SELL Signal**: Triggered when the **EMA 5** crosses below the **EMA 20** AND the 1-minute candle closes strictly below both averages.
* **Exit Rules**:
    * **Stop Loss (SL)**: 0.5%.
    * **Take Profit (TP)**: 1.0%.
    * **Reverse Exit**: Immediate closure if a signal in the opposite direction is detected.

---

## 🛠️ Installation

1.  **Clone the Repository**:
    ```bash
    git clone [https://github.com/anandyg/FIXSTRA.git](https://github.com/anandyg/FIXSTRA.git)
    cd FIXSTRA
    ```

2.  **Install Dependencies**:
    ```bash
    pip install fastapi uvicorn pandas pandas_ta kiteconnect aiohttp jinja2
    ```

3.  **Configuration**:
    Create a `settings.py` file (excluded from Git for security) and populate your API credentials and Telegram tokens.

---

## 🖥️ Usage

Run the server using Uvicorn:
```bash
python -m uvicorn app:app --port 5678 --reload"# FIXSTRA" 
