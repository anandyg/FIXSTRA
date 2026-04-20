import ccxt.pro as ccxtpro
import asyncio

async def binance_ticker(state):
    exchange = ccxtpro.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
    
    while True:
        try:
            # Multi-symbol ticker stream
            tickers = await exchange.watch_tickers(symbols)
            for symbol, tick in tickers.items():
                if symbol in state:
                    state[symbol]['ltp'] = tick['last']
                    # Calculate PnL just like we did for Nifty
                    pos = state[symbol]
                    pos['unrealized_pnl'] = (tick['last'] - pos['avg_price']) * pos['qty']
        except Exception as e:
            print(f"Crypto Ticker Error: {e}")
            await asyncio.sleep(5) # Reconnect logic