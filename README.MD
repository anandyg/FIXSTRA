# NIFTY Options Strategy Bot

A high-frequency real-time trading dashboard and automated strategy bot for NIFTY 50 and BANK NIFTY indices. This application uses FastAPI for a high-performance asynchronous backend and WebSockets for zero-latency UI updates.

## Features

- **1-Second Ticking**: Real-time market data updates every second.
- **State-Based Execution**: Advanced logic to ensure trades are executed even if the exact crossover tick is missed.
- **Dynamic Indicator Detection**: Robust handling of technical indicator column names to prevent system crashes (fixes SUPERTd KeyError).
- **Real-time PnL Tracking**: Live monitoring of Profit and Loss for active positions.
- **Automated Alerts**: Integration with Telegram for instant signal notifications.
- **Professional Dashboard**: Dark-themed, responsive UI with price pulsing and execution history.

## Technical Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn
- **Data Analysis**: Pandas, Pandas_TA
- **Data Source**: Yahoo Finance (`yfinance`)
- **Frontend**: HTML5, CSS3, JavaScript (WebSockets)

## Strategy Parameters

The bot utilizes a multi-indicator confirmation strategy:
- **EMA Crossover**: Fast EMA (9) and Slow EMA (26).
- **SuperTrend**: Trend following indicator (10 period, 3 multiplier).
- **Execution**: Signal is generated when EMA and SuperTrend align in the same direction and the state changes.

## Installation

1. **Clone the project** to your local directory (e.g., `E:\AI\paper`).
2. **Install dependencies**:
   ```bash
   pip install fastapi uvicorn pandas_ta yfinance httpx python-dotenv jinja2