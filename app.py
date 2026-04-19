import sys, os, threading, asyncio, logging, pandas as pd, pandas_ta as ta, json, aiohttp
from kiteconnect import KiteTicker
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
    "telegram_status": "Inactive", # Status indicator
    "last_processed_min": {s: -1 for s in ALL_WATCH}
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
    """Sends message and updates status on success"""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    state["telegram_status"] = "Active"
                else:
                    state["telegram_status"] = "Inactive"
                    logger.error(f"Telegram Error: {resp.status}")
        except Exception as e:
            state["telegram_status"] = "Inactive"
            logger.error(f"Telegram Exception: {e}")

async def fetch_history():
    """Pre-load history to avoid 'COLLECTING' wait"""
    async with aiohttp.ClientSession() as session:
        for sym in settings.CRYPTO_SYMBOLS:
            try:
                async with session.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1m&limit=100") as resp:
                    data = await resp.json()
                    df = pd.DataFrame(data, columns=['t','O','H','L','Close','V','CT','QV','Tr','BB','BQ','I'])
                    df['Close'] = df['Close'].astype(float)
                    state["dfs"][sym] = df[['Close']].tail(100)
                    state["open_prices"][sym] = df['Close'].iloc[0]
            except: logger.error(f"History Sync Fail: {sym}")

def run_strategy(symbol, price):
    """EMA 5/20 Closing Basis Logic"""
    df = state["dfs"][symbol] = pd.concat([state["dfs"][symbol], pd.DataFrame([{"Close": price}])]).tail(100)
    if len(df) < 21: return "NEUTRAL"
    
    ema5 = ta.ema(df['Close'], length=5)
    ema20 = ta.ema(df['Close'], length=20)
    
    c_p, c_5, c_20 = df['Close'].iloc[-1], ema5.iloc[-1], ema20.iloc[-1]
    p_5, p_20 = ema5.iloc[-2], ema20.iloc[-2]

    # BUY: Cross UP + Price Close > both EMAs
    if p_5 <= p_20 and c_5 > c_20 and c_p > c_5 and c_p > c_20: return "BUY"
    # SELL: Cross DOWN + Price Close < both EMAs
    if p_5 >= p_20 and c_5 < c_20 and c_p < c_5 and c_p < c_20: return "SELL"
    return "NEUTRAL"

async def calculate_portfolio():
    """Combined PnL: Realized + Floating"""
    inv, val, unrealized = 0.0, 0.0, 0.0
    for sym, side in state["active_pos"].items():
        if side:
            qty = settings.TRADE_QTY.get(sym, 1)
            entry = state["targets"][sym]["entry"]
            lp = state["live_prices"].get(sym, entry)
            inv += (entry * qty)
            val += (lp * qty)
            unrealized += (lp - entry) * qty if side == "BUY" else (entry - lp) * qty
    state["total_investment"], state["current_value"] = round(inv, 2), round(val, 2)
    state["total_pnl_combined"] = round(state["running_pnl"] + unrealized, 2)

def execute_trade_engine(symbol, price, signal):
    """SL 5% / TP 10% - No Reverse Exit"""
    if state["active_pos"].get(symbol):
        t = state["targets"][symbol]; side = state["active_pos"][symbol]; exit_type = None
        sl_lvl = t["entry"] * (0.95 if side == "BUY" else 1.05)
        tp_lvl = t["entry"] * (1.10 if side == "BUY" else 0.90)
        
        if (side == "BUY" and price <= sl_lvl) or (side == "SELL" and price >= sl_lvl): exit_type = "🚨 SL EXIT"
        elif (side == "BUY" and price >= tp_lvl) or (side == "SELL" and price <= tp_lvl): exit_type = "💰 TP EXIT"

        if exit_type:
            pnl = (price - t["entry"]) if side == "BUY" else (t["entry"] - price)
            state["running_pnl"] += pnl
            state["trades"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "symbol": symbol, "type": exit_type, "entry": t["entry"], "exit": price, "pnl": round(pnl, 2)})
            asyncio.create_task(send_telegram_msg(f"{exit_type} | {symbol} Closed @ {price}"))
            state["active_pos"][symbol] = None

    if not state["active_pos"].get(symbol) and signal in ["BUY", "SELL"]:
        state["active_pos"][symbol] = signal
        state["targets"][symbol] = {"entry": price}
        state["trades"].insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"), # Order timestamp
            "symbol": symbol, "type": signal, "entry": price, "exit": "OPEN", "pnl": 0.0
        })
        asyncio.create_task(send_telegram_msg(f"🚀 *NEW TRADE* | {signal} | {symbol} @ {price}"))

# --- 5. TASKS ---
async def binance_task():
    url = "wss://stream.binance.com:9443/stream?streams=" + "/".join([f"{s.lower()}@ticker" for s in settings.CRYPTO_SYMBOLS])
    async with aiohttp.ClientSession() as sess:
        async with sess.ws_connect(url) as ws:
            state["market_status"] = "LIVE: BINANCE"
            async for msg in ws:
                d = json.loads(msg.data)
                sym, lp = d['stream'].split('@')[0].upper(), float(d['data']['c'])
                state["live_prices"][sym] = lp
                
                # Verify 1-minute closure
                cur_min = datetime.now().minute
                if cur_min != state["last_processed_min"][sym]:
                    if state["last_processed_min"][sym] != -1:
                        execute_trade_engine(sym, lp, run_strategy(sym, lp))
                    state["last_processed_min"][sym] = cur_min
                await calculate_portfolio()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_history()
    asyncio.create_task(send_telegram_msg("🚀 *FIXSTRA SYSTEM ONLINE*"))
    async def hb():
        while True:
            state["last_update"] = datetime.now().strftime("%H:%M:%S")
            await manager.broadcast({k: v for k, v in state.items() if k != "dfs"})
            await asyncio.sleep(1)
    asyncio.create_task(hb()); asyncio.create_task(binance_task())
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