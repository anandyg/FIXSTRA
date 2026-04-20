# Constants in settings.py or at the top of app.py
MAX_DRAWDOWN_PCT = -2.0  # -2% is the standard professional limit
CAPITAL_BASE = 100000.0   # Adjust based on your actual trading capital

async def risk_monitor_loop():
    while True:
        total_pnl = sum(pos['unrealized_pnl'] for pos in state.values())
        current_dd = (total_pnl / CAPITAL_BASE) * 100

        if current_dd <= MAX_DRAWDOWN_PCT:
            logger.critical(f"⚠️ RISK BREACH: Drawdown at {current_dd:.2f}%. Executing Auto-Panic!")
            await exit_all_positions()
            # Send Telegram Alert immediately
            await send_telegram_alert(f"FIXSTRA AUTO-EXIT: Portfolio DD hit {current_dd:.2f}%")
            break # Stop monitoring to prevent loop-firing; requires manual reset
        
        await asyncio.sleep(1) # Monitor every second