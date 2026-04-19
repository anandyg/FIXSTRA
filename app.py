import sys, os, threading, asyncio, logging, pandas as pd, pandas_ta as ta, json, aiohttp
from kiteconnect import KiteConnect, KiteTicker
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import settings

# --- 1. SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
base_dir = os.path.dirname(os.path.abspath(__file__))
template_path = os.path.join(base_dir, "templates")

# --- 2. GLOBAL STATE ---
ALL_WATCH = list(settings.INDIAN_SYMBOLS.values()) + settings.CRYPTO_SYMBOLS
state = {
    "mode": settings.DEFAULT_MODE,
    "live_prices": {s: 0.0 for s in ALL_WATCH},
    "open_prices": {s: 0.0 for s in ALL_WATCH},
    "total_investment": 0.0, "current_value": 0.0, "total_pnl_combined": 0.0,
    "running_pnl": 0.0, "market_status": "INITIALIZING", "last_update": "00:00:00",
    "trades": [], "dfs": {s: pd.DataFrame() for s in ALL_WATCH}, 
    "active_pos": {}, "targets": {},
    "telegram_status": "Inactive", "telegram_logs": []
}

# --- 3. CONNECTION MANAGER ---
class ConnectionManager:
    def __init__(self): self.active_connections = []
    async def connect(self, ws): await ws.accept(); self.active_connections.append(ws)
    def disconnect(self, ws): 
        if ws in self.active_connections: self.active_connections.remove(ws)
    async def broadcast(self, msg):
        for connection in self.active_connections:
            try: await connection.send_json(msg)
            except: self.active_connections.remove(connection)

manager = ConnectionManager()

# --- 4. ENGINE LOGIC ---
async def send_telegram_msg(msg):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}) as resp:
                if resp.status == 200: state["telegram_status"] = "Active"
        except: state["telegram_status"] = "Inactive"

async def fetch_history():
    """Syncs 100 minutes of history for immediate crossover checking"""
    state["market_status"] = "SYNCING HISTORY..."
    async with aiohttp.ClientSession() as session:
        for sym in settings.CRYPTO_SYMBOLS:
            try:
                async with session.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1m&limit=100") as resp:
                    data = await resp.json()
                    df = pd.DataFrame(data, columns=['t','O','H','L','Close','V','CT','QV','Tr','BB','BQ','I'])
                    df['Close'] = df['Close'].astype(float)
                    state["dfs"][sym] = df[['Close']].tail(100)
                    state["open_prices"][sym] = df['Close'].iloc[0]
                    logger.info(f"✅ Pre-loaded {sym} History")
            except: logger.error(f"History Sync Fail: {sym}")

def run_strategy(symbol, price):
    """EMA 5/20 Crossover + 1-Min Closing Basis Logic"""
    df = state["dfs"][symbol] = pd.concat([state["dfs"][symbol], pd.DataFrame([{"Close": price}])]).tail(100)
    
    # Require at least 21 candles for EMA 20 stability
    if len(df) < 21: return "COLLECTING"
    
    ema5 = ta.ema(df['Close'], length=5)
    ema20 = ta.ema(df['Close'], length=20)
    
    c_p, c_5, c_20 = df['Close'].iloc[-1], ema5.iloc[-1], ema20.iloc[-1]
    p_5, p_20 = ema5.iloc[-2], ema20.iloc[-2]

    # BUY: Cross UP + Price Closing Above both EMAs
    if p_5 <= p_20 and c_5 > c_20:
        if c_p > c_5 and c_p > c_20: return "BUY"
    
    # SELL: Cross DOWN + Price Closing Below both EMAs
    if p_5 >= p_20 and c_5 < c_20:
        if c_p < c_5 and c_p < c_20: return "SELL"
        
    return "NEUTRAL"

async def calculate_portfolio():
    """Combined PnL calculation for main dashboard cards"""
    inv, val = 0.0, 0.0
    for sym, side in state["active_pos"].items():
        if side:
            qty = settings.TRADE_QTY.get(sym, 1)
            lp = state["live_prices"].get(sym, state["targets"][sym]["entry"])
            inv += (state["targets"][sym]["entry"] * qty)
            val += (lp * qty)
    state["total_investment"], state["current_value"] = round(inv, 2), round(val, 2)
    state["total_pnl_combined"] = round(state["running_pnl"] + (val - inv), 2)

def execute_trade_engine(symbol, price, signal):
    """Handles SL/TP exits and Reverse Signal closures"""
    if state["active_pos"].get(symbol):
        t = state["targets"][symbol]; side = state["active_pos"][symbol]; exit_type = None
        if (side == "BUY" and price <= t["sl"]) or (side == "SELL" and price >= t["sl"]): exit_type = "🚨 SL EXIT"
        elif (side == "BUY" and price >= t["tp"]) or (side == "SELL" and price <= t["tp"]): exit_type = "💰 TP EXIT"
        elif signal in ["BUY", "SELL"] and signal != side: exit_type = "🔄 REVERSE EXIT"

        if exit_type:
            pnl = (price - t["entry"]) if side == "BUY" else (t["entry"] - price)
            state["running_pnl"] += pnl
            state["trades"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "symbol": symbol, "type": exit_type, "entry": t["entry"], "exit": price, "pnl": round(pnl, 2)})
            asyncio.create_task(send_telegram_msg(f"{exit_type} | {symbol} Closed @ {price}\nPnL: {round(pnl, 2)}"))
            state["active_pos"][symbol] = None

    if not state["active_pos"].get(symbol) and signal in ["BUY", "SELL"]:
        sl_m = (1 - settings.SL_PERCENT/100) if signal == "BUY" else (1 + settings.SL_PERCENT/100)
        tp_m = (1 + settings.TP_PERCENT/100) if signal == "BUY" else (1 - settings.TP_PERCENT/100)
        state["active_pos"][symbol] = signal
        state["targets"][symbol] = {"entry": price, "sl": price * sl_m, "tp": price * tp_m}
        state["trades"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "symbol": symbol, "type": signal, "entry": price, "exit": "OPEN", "pnl": 0.0})
        asyncio.create_task(send_telegram_msg(f"🚀 *NEW TRADE* | {signal} | {symbol} @ {price}"))

# --- 5. DATA TASKS ---
async def binance_task():
    url = "wss://stream.binance.com:9443/stream?streams=" + "/".join([f"{s.lower()}@ticker" for s in settings.CRYPTO_SYMBOLS])
    while True:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.ws_connect(url) as ws:
                    state["market_status"] = "LIVE: BINANCE"
                    async for msg in ws:
                        if state["mode"] != "CRYPTO": break
                        d = json.loads(msg.data)
                        sym, lp = d['stream'].split('@')[0].upper(), float(d['data']['c'])
                        state["live_prices"][sym] = lp
                        if state["open_prices"].get(sym, 0) == 0: state["open_prices"][sym] = lp
                        execute_trade_engine(sym, lp, run_strategy(sym, lp))
                        await calculate_portfolio()
        except: state["market_status"] = "BINANCE RECONNECTING..."
        await asyncio.sleep(5)

# --- 6. LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    await fetch_history()
    asyncio.create_task(send_telegram_msg("🚀 *FIXSTRA SYSTEM ONLINE*"))
    async def hb():
        while True:
            state["last_update"] = datetime.now().strftime("%H:%M:%S")
            await manager.broadcast({k: v for k, v in state.items() if k != "dfs"})
            await asyncio.sleep(1)
    asyncio.create_task(hb())
    asyncio.create_task(binance_task())
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=template_path)
@app.get("/")
async def index(request: Request): return templates.TemplateResponse(request=request, name="index.html")
@app.websocket("/ws")
async def ws_ep(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True: await ws.receive_text()
    except: manager.disconnect(ws)