const socket = new WebSocket(`ws://${window.location.hostname}:5678/ws`);
const positionsList = document.getElementById('positions-list');
const hbDot = document.getElementById('heartbeat');

socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    // Update Heartbeat UI
    hbDot.style.color = '#00ff41';
    setTimeout(() => hbDot.style.color = 'grey', 200);

    // Process each position in the broadcast
    Object.keys(data).forEach(symbol => {
        if (symbol === 'dfs') return; // Skip non-position data
        updatePositionRow(symbol, data[symbol]);
    });
};

function updatePositionRow(symbol, pos) {
    let row = document.getElementById(`pos-${symbol}`);
    
    // 1. Create row if it doesn't exist
    if (!row) {
        row = document.createElement('div');
        row.id = `pos-${symbol}`;
        row.className = 'position-card';
        positionsList.appendChild(row);
    }

    // 2. Determine Color and Sign
    const pnl = pos.unrealized_pnl.toFixed(2);
    const pnlClass = pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
    const prefix = pnl >= 0 ? '+' : '';

    // 3. Optimized DOM Injection
    row.innerHTML = `
        <div>
            <div style="font-weight: bold; font-size: 1.2em;">${symbol}</div>
            <div style="color: var(--text-gray); font-size: 0.8em;">Qty: ${pos.qty} | Avg: ${pos.avg_price.toFixed(2)}</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 0.9em; color: var(--text-gray);">LTP: ${pos.ltp.toFixed(2)}</div>
            <div class="${pnlClass}" style="font-size: 1.4em; font-weight: bold;">
                ${prefix}${pnl} (${pos.pnl_percentage.toFixed(2)}%)
            </div>
        </div>
    `;
}

// Keep track of what we've already journaled this session
const journaledSymbols = new Set();

function updatePositionRow(symbol, pos) {
    // ... (previous logic for updating PnL) ...

    // Auto-trigger Journaling when position closes
    if (pos.qty === 0 && !journaledSymbols.has(symbol)) {
        triggerJournal(symbol);
    }
}

function triggerJournal(symbol) {
    journaledSymbols.add(symbol);
    document.getElementById('journal-symbol').innerText = symbol;
    document.getElementById('form-symbol').value = symbol;
    document.getElementById('journal-modal').style.display = 'flex';
}

// Handle Form Submission
document.getElementById('journal-form').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
        symbol: document.getElementById('form-symbol').value,
        strategy: document.getElementById('form-strategy').value,
        emotion: document.getElementById('form-emotion').value,
        notes: document.getElementById('form-notes').value,
        timestamp: new Date().toISOString()
    };

    const response = await fetch('/api/journal', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });

    if (response.ok) {
        document.getElementById('journal-modal').style.display = 'none';
        console.log("Journal Saved to OCI Storage");
    }
};


document.getElementById('panic-button').onclick = async () => {
    const confirmExit = confirm("CRITICAL: This will close ALL open positions and cancel ALL pending orders. Proceed?");
    
    if (confirmExit) {
        const response = await fetch('/api/exit-all', { method: 'POST' });
        const result = await response.json();
        
        if (response.ok) {
            alert(`Panic Exit Triggered: ${result.closed_count} positions closed.`);
        } else {
            alert("Error triggering panic exit. Check server logs!");
        }
    }
};



// Inside socket.onmessage
const totalPnl = Object.values(data).reduce((acc, pos) => acc + (pos.unrealized_pnl || 0), 0);
const ddPct = (totalPnl / 100000) * 100; // Match your CAPITAL_BASE

const bar = document.getElementById('risk-bar-fill');
const val = document.getElementById('risk-value');

// Update UI
const displayPct = Math.min(Math.abs(ddPct / 2) * 100, 100); // 2 is our MAX_DRAWDOWN_PCT
bar.style.width = `${displayPct}%`;
val.innerText = `${ddPct.toFixed(2)}% / -2.00%`;

// Change color to Yellow then Red as risk increases
if (ddPct < -1.0) bar.style.background = '#f1c40f'; // Warning
if (ddPct < -1.5) bar.style.background = '#e74c3c'; // Danger