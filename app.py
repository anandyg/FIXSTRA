import os, asyncio, logging, pandas as pd, pandas_ta as ta, requests
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from kiteconnect import KiteTicker, KiteConnect
from engine import LifecycleEngine
from models import Fill
import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FIXSTRA")
base_dir = os.path.dirname(os.path.abspath(__file__))

class ConnectionManager:
    def __init__(self): self.active_connections = []
    async def connect(self, ws): await ws.accept(); self.active_connections.append(ws)
    def disconnect(self, ws): 
        if ws in self.active_connections: self.active_connections.remove(ws)
    async def broadcast(self, msg):
        for conn in self.active_connections[:]:
            try: await conn.send_json(msg)
            except: self.disconnect(conn)

engine = LifecycleEngine()
manager = ConnectionManager()
kite = KiteConnect(api_key=settings.KITE_API_KEY)
kite.set_access_token(settings.KITE_ACCESS_TOKEN)

SYMBOLS = list(settings.INDIAN_SYMBOLS.values())
TOKENS = {int(k): v for k, v in settings.INDIAN_SYMBOLS.items()}

state = {
    "live_prices": {s: 0.0 for s in SYMBOLS},
    "dfs": {s: pd.DataFrame() for s in SYMBOLS},
    "market_status": "INITIALIZING",
    "telegram_status": "READY",
    "last_update": "00:00:00"
}

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, data={"chat_id": settings.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
        state["telegram_status"] = "CONNECTED" if res.status_code == 200 else "ERR"
    except: state["telegram_status"] = "OFFLINE"

def on_ticks(ws, ticks):
    state["market_status"] = "LIVE: KITE"
    for tick in ticks:
        sym = TOKENS.get(tick['instrument_token'])
        if not sym: continue
        lp = tick['last_price']
        state["live_prices"][sym] = lp
        
        # 1. RISK MONITORING (SL/TP)
        if sym in engine.positions:
            pos = engine.positions[sym]
            hit_tp = (pos['side'] == "BUY" and lp >= pos['tp']) or (pos['side'] == "SELL" and lp <= pos['tp'])
            hit_sl = (pos['side'] == "BUY" and lp <= pos['sl']) or (pos['side'] == "SELL" and lp >= pos['sl'])
            if hit_tp or hit_sl:
                exit_reason = "TP_EXIT" if hit_tp else "SL_EXIT"
                engine.close_position(sym, lp, exit_reason)

        # 2. SIGNAL LOGIC
        df = state["dfs"][sym] = pd.concat([state["dfs"][sym], pd.DataFrame([{"Close": lp}])]).tail(250)
        if len(df) >= 200 and sym not in engine.positions:
            ema20, ema200 = ta.ema(df['Close'], 20).iloc[-1], ta.ema(df['Close'], 200).iloc[-1]
            qty = max(1, settings.TRADE_CAPITAL_LIMIT // lp)
            if ema20 > ema200 and lp > ema20 and lp > ema200: # BUY
                sl, tp = lp * (1 - settings.SL_PCT), lp * (1 + settings.TP_PCT)
                engine.open_position(Fill(fill_id=f"B_{int(datetime.now().timestamp())}", symbol=sym, side="BUY", qty=qty, price=lp, value=qty*lp, sl_price=sl, tp_price=tp))
                send_telegram(f"🚀 *BUY*: {sym} @ ₹{lp}")
            elif ema20 < ema200 and lp < ema20 and lp < ema200: # SELL
                sl, tp = lp * (1 + settings.SL_PCT), lp * (1 - settings.TP_PCT)
                engine.open_position(Fill(fill_id=f"S_{int(datetime.now().timestamp())}", symbol=sym, side="SELL", qty=qty, price=lp, value=qty*lp, sl_price=sl, tp_price=tp))
                send_telegram(f"📉 *SELL*: {sym} @ ₹{lp}")

def on_connect(ws, response):
    state["market_status"] = "LIVE: KITE"
    ws.subscribe(list(TOKENS.keys())); ws.set_mode(ws.MODE_FULL, list(TOKENS.keys()))

@asynccontextmanager
async def lifespan(app: FastAPI):
    kws = KiteTicker(settings.KITE_API_KEY, settings.KITE_ACCESS_TOKEN)
    kws.on_ticks, kws.on_connect = on_ticks, on_connect
    kws.connect(threaded=True)
    async def loop():
        while True:
            try:
                # FIXED: Calculate ALL P&L fields for the dashboard
                realized = sum(t['pnl'] for t in engine.closed_trades)
                unrealized = sum((state["live_prices"][s] - p['avg_price']) * p['qty'] * (1 if p['side'] == "BUY" else -1) 
                                 for s, p in engine.positions.items() if state["live_prices"][s] > 0)
                
                await manager.broadcast({
                    "market_status": state["market_status"], "telegram_status": state["telegram_status"],
                    "live_prices": state["live_prices"], "open_positions": engine.positions,
                    "closed_trades": engine.closed_trades[-10:], "realized_pnl": round(realized, 2),
                    "unrealized_pnl": round(unrealized, 2), "combined_pnl": round(realized + unrealized, 2),
                    "last_update": datetime.now().strftime("%H:%M:%S")
                })
            except: pass
            await asyncio.sleep(1)
    asyncio.create_task(loop()); yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

@app.get("/")
async def index(request: Request): return templates.TemplateResponse(request=request, name="index.html")

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws); 
    try: 
        while True: await ws.receive_text()
    except WebSocketDisconnect: manager.disconnect(ws)