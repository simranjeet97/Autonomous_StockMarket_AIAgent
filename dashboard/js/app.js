/**
 * app.js
 * ──────
 * Main application logic for the AI Trading Dashboard.
 * Handles: real-time clock, market status, candlestick chart,
 * volume chart, market data simulation, signal feed, trade log,
 * risk gauge updates, OPS meter, and overall state management.
 */

'use strict';

// ── App State ─────────────────────────────────────────────────────────────────
const state = {
  symbol:    'RELIANCE',
  timeframe: '1d',
  dailyPnl:  0,
  positions: 0,
  ordersToday: 0,
  sessionStart: Date.now(),
  lastSignal: null,
  opsRate: 0,
  candles: [],
};

// ── Market Data Simulation ────────────────────────────────────────────────────
const MOCK_PRICES = {
  RELIANCE: 2950, TCS: 3800, INFY: 1780, HDFCBANK: 1650,
  ICICIBANK: 1120, SBIN: 800, WIPRO: 565, BAJFINANCE: 7200,
};

function getBasePrice(symbol) {
  return MOCK_PRICES[symbol] || 1000;
}

function generateCandle(prev, base) {
  const volatility = base * 0.012;
  const open  = prev ? prev.close : base + (Math.random() - 0.5) * volatility;
  const close = open + (Math.random() - 0.5) * volatility;
  const high  = Math.max(open, close) + Math.random() * volatility * 0.5;
  const low   = Math.min(open, close) - Math.random() * volatility * 0.5;
  const volume = Math.floor(Math.random() * 5_000_000 + 500_000);
  return { open: +open.toFixed(2), high: +high.toFixed(2), low: +low.toFixed(2), close: +close.toFixed(2), volume };
}

function generateHistory(symbol, count = 60) {
  const base = getBasePrice(symbol);
  const now  = Date.now();
  const MS_PER_DAY = 86_400_000;
  const candles = [];
  for (let i = count; i >= 0; i--) {
    const ts = new Date(now - i * MS_PER_DAY);
    const prev = candles[candles.length - 1] || null;
    candles.push({ x: ts, ...generateCandle(prev, base) });
  }
  return candles;
}

// ── Chart Setup ──────────────────────────────────────────────────────────────
let candleChart, volumeChart;

function initCharts() {
  const canvasC = document.getElementById('candleChart');
  const canvasV = document.getElementById('volumeChart');
  if (!canvasC || !canvasV) return;

  const GREEN = '#00ff88', RED = '#ef4444', GREY = 'rgba(255,255,255,0.05)';
  const gridLine = { color: 'rgba(255,255,255,0.04)', lineWidth: 1 };

  // ── Candlestick ────────────────────────────────────────────────
  try {
    candleChart = new Chart(canvasC, {
      type: 'candlestick',
      data: { datasets: [{ label: state.symbol, data: [], color: { up: GREEN, down: RED, unchanged: '#6b7280' }, borderColor: { up: GREEN, down: RED, unchanged: '#6b7280' } }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          x: { type: 'time', time: { unit: 'day' }, grid: gridLine, ticks: { color: '#4a5568', font: { family: 'JetBrains Mono', size: 10 } } },
          y: { position: 'right', grid: gridLine, ticks: { color: '#4a5568', font: { family: 'JetBrains Mono', size: 10 }, callback: v => '₹' + v.toLocaleString('en-IN') } },
        },
        plugins: { legend: { display: false }, tooltip: {
          backgroundColor: 'rgba(17,24,39,0.95)',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          callbacks: {
            label: ctx => {
              const r = ctx.raw;
              return [`O: ₹${r.o}  H: ₹${r.h}`, `L: ₹${r.l}  C: ₹${r.c}`];
            }
          }
        }},
      }
    });
  } catch (e) {
    // Fall back to line chart if financial plugin not loaded
    candleChart = new Chart(canvasC, {
      type: 'line',
      data: { datasets: [{ label: state.symbol, data: [], borderColor: GREEN, backgroundColor: 'rgba(0,255,136,0.05)', borderWidth: 2, pointRadius: 0, tension: 0.3 }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          x: { type: 'time', time: { unit: 'day' }, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#4a5568', font: { size: 10 } } },
          y: { position: 'right', grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#4a5568', callback: v => '₹' + v.toLocaleString('en-IN') } },
        },
        plugins: { legend: { display: false } },
      }
    });
  }

  // ── Volume ─────────────────────────────────────────────────────
  volumeChart = new Chart(canvasV, {
    type: 'bar',
    data: { datasets: [{ label: 'Volume', data: [], backgroundColor: 'rgba(0,255,136,0.15)', borderColor: 'transparent', borderRadius: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: {
        x: { type: 'time', time: { unit: 'day' }, display: false },
        y: { display: false },
      },
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => `Vol: ${(ctx.raw.y / 1e5).toFixed(1)}L` }
      }},
    }
  });
}

async function loadSymbolData(symbol) {
  state.symbol = symbol;
  
  try {
    const res = await fetch(`http://localhost:8000/api/history/${symbol}`);
    const data = await res.json();
    if (data.bars && data.bars.length > 0) {
      state.candles = data.bars.map(b => ({
        x: new Date(b.timestamp),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
        volume: b.volume
      }));
    } else {
      state.candles = [];
    }
  } catch (err) {
    console.error("Error fetching history:", err);
    state.candles = [];
  }

  if (!candleChart || !volumeChart) return;

  // Update candlestick data
  try {
    if (candleChart.config.type === 'candlestick') {
      candleChart.data.datasets[0].data = state.candles.map(c => ({
        x: c.x, o: c.open, h: c.high, l: c.low, c: c.close
      }));
    } else {
      candleChart.data.datasets[0].data = state.candles.map(c => ({ x: c.x, y: c.close }));
    }
    candleChart.data.datasets[0].label = symbol;
    candleChart.update('none');
  } catch(e) {}

  // Update volume
  try {
    volumeChart.data.datasets[0].data = state.candles.map(c => ({ x: c.x, y: c.volume }));
    volumeChart.update('none');
  } catch(e) {}

  // Update ticker (use last candle)
  const last = state.candles[state.candles.length - 1];
  const prev = state.candles[state.candles.length - 2];
  if (last) {
    const chg    = last.close - (prev?.close || last.open);
    const chgPct = (chg / (prev?.close || last.open) * 100).toFixed(2);
    document.getElementById('tickerSymbol').textContent = symbol;
    document.getElementById('tickerPrice').textContent  = '₹' + last.close.toLocaleString('en-IN');
    const tc = document.getElementById('tickerChange');
    tc.textContent  = (chg >= 0 ? '+' : '') + chgPct + '%';
    tc.className    = 'ticker-change ' + (chg >= 0 ? 'positive' : 'negative');
    document.getElementById('tickerHigh').textContent  = '₹' + last.high.toLocaleString('en-IN');
    document.getElementById('tickerLow').textContent   = '₹' + last.low.toLocaleString('en-IN');
    document.getElementById('tickerVol').textContent   = (last.volume / 1e5).toFixed(1) + 'L';
  }
}

// ── Scan / Analysis Simulation ────────────────────────────────────────────────
function analyzeSymbol(symbol) {
  const base = getBasePrice(symbol);
  const last = state.candles[state.candles.length - 1];
  const price = last?.close || base;

  // Simulate RSI
  const rsi = 25 + Math.random() * 55; // range 25–80
  const rsiSignal = rsi < 30 ? 'oversold' : rsi > 70 ? 'overbought' : 'neutral';

  // Simulate MACD
  const macdLine = (Math.random() - 0.5) * 10;
  const signalLine = macdLine - (Math.random() - 0.5) * 3;
  const hist = macdLine - signalLine;
  const macdCross = hist > 0 ? 'bullish_crossover' : 'bearish_crossover';

  // Simulate Bollinger
  const bbSignal = rsi < 30 ? 'oversold_bounce' : rsi > 70 ? 'overbought_squeeze' : 'within_bands';

  // Score
  let buy = 0, sell = 0;
  if (rsiSignal === 'oversold')   buy++;
  if (rsiSignal === 'overbought') sell++;
  if (macdCross.includes('bullish')) buy++;
  if (macdCross.includes('bearish')) sell++;
  if (bbSignal === 'oversold_bounce')    buy++;
  if (bbSignal === 'overbought_squeeze') sell++;

  const rec = buy >= 2 ? 'BUY' : sell >= 2 ? 'SELL' : 'HOLD';

  return {
    symbol,
    recommendation: rec,
    confidence: `${Math.max(buy, sell)}/3 indicators agree`,
    rsi:     { rsi: +rsi.toFixed(1), signal: rsiSignal },
    macd:    { crossover_signal: macdCross, histogram: +hist.toFixed(3) },
    bollinger:{ signal: bbSignal },
    price,
  };
}

// ── Main Scan Trigger ─────────────────────────────────────────────────────────
async function triggerScan() {
  const symbol = document.getElementById('symbolSelect').value;
  const btn    = document.getElementById('scanBtn');
  btn.classList.add('scanning');
  btn.disabled = true;

  try {
    // 1. Root & Analyst
    resetAllAgents();
    setAgentState('root', AgentState.RUNNING);
    await new Promise(r => setTimeout(r, 400));
    setAgentState('root', AgentState.DONE);
    
    setAgentState('analyst', AgentState.RUNNING);
    
    const aRes = await fetch(`http://localhost:8000/api/scan/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: symbol })
    });
    
    if (!aRes.ok) {
        const errData = await aRes.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${aRes.status}`);
    }

    const analystData = await aRes.json();
    const signal = analystData.signal;

    if (!signal) throw new Error("No signal data received from analyst");

    updateAnalystStats(signal);
    addSignalFeedItem(signal);
    setAgentState('analyst', AgentState.DONE);
    
    state.lastSignal = signal;

    // 2. Risk check
    if (signal.recommendation !== 'HOLD') {
        setAgentState('risk', AgentState.RUNNING);
        const rRes = await fetch(`http://localhost:8000/api/scan/risk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: symbol })
        });

        if (!rRes.ok) {
            const errData = await rRes.json().catch(() => ({}));
            throw new Error(errData.detail || `Risk API error: ${rRes.status}`);
        }

        const riskData = await rRes.json();
        
        updateRiskRules(riskData.rule_checks);
        setAgentState('risk', riskData.approved ? AgentState.DONE : AgentState.BLOCKED);

        // Show signal banner
        renderSignalBanner(signal, riskData.approved);

        // If auto-execute (approved + BUY/SELL)
        if (riskData.approved) {
            setAgentState('execution', AgentState.RUNNING);
            await new Promise(r => setTimeout(r, 600));
            
            addTradeLogEntry(signal);
            state.ordersToday++;
            state.positions++;
            const pnlDelta = (Math.random() - 0.4) * 500;
            state.dailyPnl += pnlDelta;
            updatePnlDisplay();
            updateOpsGauge(1);
            showToast('Order Submitted', `${signal.recommendation} ${symbol} — Executed limit order`, 'success');
            setAgentState('execution', AgentState.DONE);
        } else {
            showToast('Risk Blocked', 'Trade rejected by Risk Agent.', 'error');
        }
    } else {
        renderSignalBanner(signal, false);
    }
  } catch (error) {
      console.error("Manual Scan API Error:", error);
      showToast("Scan Failed", error.message || "Failed to connect to backend", "error");
      // Reset agents on error
      setAgentState('analyst', AgentState.BLOCKED);
      if (state.agentStates?.risk === 'RUNNING') setAgentState('risk', AgentState.BLOCKED);
  } finally {
      btn.classList.remove('scanning');
      btn.disabled = false;
  }
}

async function executeSignal() {
  if (!state.lastSignal) return;
  const s = state.lastSignal;
  const btn = document.getElementById('executeBtn');
  btn.disabled = true;
  btn.innerHTML = 'Executing...';
  
  try {
    setAgentState('execution', AgentState.RUNNING);
    
    const res = await fetch(`http://localhost:8000/api/scan/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: s.symbol, order_type: s.recommendation, price: s.price })
    });
    const execData = await res.json();
    
    if (execData.status === 'success' || execData.status === 'OPEN' || execData.status === 'PENDING' || execData.status === 'COMPLETE') {
      fetchTradeLogs();
      showToast('Order Submitted', `${s.recommendation} ${s.symbol}`, 'success');
      document.getElementById('signalBanner').style.display = 'none';
      setAgentState('execution', AgentState.DONE);
    } else {
      showToast('Execution Failed', execData.message || 'Broker rejected order', 'error');
      setAgentState('execution', AgentState.BLOCKED);
    }
  } catch (err) {
    console.error("Execution error:", err);
    showToast('Execution Error', 'Failed to reach backend', 'error');
    setAgentState('execution', AgentState.BLOCKED);
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Execute Trade';
  }
}

// ── UI Renderers ──────────────────────────────────────────────────────────────
function renderSignalBanner(signal, approved) {
  const banner = document.getElementById('signalBanner');
  const icon   = document.getElementById('signalIcon');
  const rec    = document.getElementById('signalRec');
  const conf   = document.getElementById('signalConf');
  const execBtn= document.getElementById('executeBtn');

  if (!banner) return;
  banner.style.display = 'flex';

  const icons = { BUY: '🚀', SELL: '📉', HOLD: '⏸️' };
  icon.textContent = icons[signal.recommendation] || '📊';
  rec.textContent  = signal.recommendation;
  rec.className    = 'signal-rec ' + signal.recommendation.toLowerCase();
  conf.textContent = signal.confidence + (approved ? ' · Risk APPROVED ✅' : ' · Risk BLOCKED 🚫');

  execBtn.style.display = approved && signal.recommendation !== 'HOLD' ? 'inline-flex' : 'none';

  // Update banner border
  const colors = { BUY: 'rgba(0,255,136,0.3)', SELL: 'rgba(239,68,68,0.3)', HOLD: 'rgba(245,158,11,0.3)' };
  banner.style.borderColor = approved ? (colors[signal.recommendation] || 'var(--border)') : 'rgba(239,68,68,0.3)';
}

function addSignalFeedItem(signal) {
  const feed = document.getElementById('signalFeed');
  if (!feed) return;

  // Remove placeholder
  const placeholder = feed.querySelector('.feed-placeholder');
  if (placeholder) placeholder.remove();

  const now  = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const item = document.createElement('div');
  item.className = `feed-item ${signal.recommendation.toLowerCase()}`;
  const colors = { BUY: 'color:#00ff88', SELL: 'color:#ef4444', HOLD: 'color:#f59e0b' };
  item.innerHTML = `
    <span class="feed-time">${now}</span>
    <span class="feed-sym" style="margin-left:6px">${signal.symbol}</span>
    <span class="feed-rec" style="${colors[signal.recommendation]}">${signal.recommendation}</span>
    <div style="font-size:0.68rem;color:#4a5568;margin-top:2px">${signal.confidence}</div>`;
  feed.prepend(item);

  // Keep max 20 items
  while (feed.children.length > 20) feed.lastChild.remove();
}

function addTradeLogEntry(signal) {
  const tbody = document.getElementById('tradeLogBody');
  if (!tbody) return;

  // Remove "no trades" placeholder
  const empty = tbody.querySelector('.empty-row');
  if (empty) empty.parentElement.remove();

  const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  const tr  = document.createElement('tr');
  const isBuy = signal.recommendation === 'BUY';
  tr.innerHTML = `
    <td style="font-family:var(--font-mono)">${now}</td>
    <td>${signal.symbol}</td>
    <td class="${isBuy ? 'badge-buy' : 'badge-sell'}">${signal.recommendation}</td>
    <td>1</td>
    <td class="badge-ok">STUB</td>`;
  tbody.prepend(tr);

  document.getElementById('ordersToday').textContent = state.ordersToday;
  document.getElementById('lastOrder').textContent   = `${signal.recommendation} ${signal.symbol}`;
}

async function fetchTradeLogs() {
  try {
    const res = await fetch(`http://localhost:8000/api/trade_logs`);
    const data = await res.json();
    if (data.status === 'success' && data.logs) {
      const tbody = document.getElementById('tradeLogBody');
      if (!tbody) return;
      
      if (data.logs.length > 0) {
        tbody.innerHTML = data.logs.map(log => {
          const isBuy = log.order_type === 'BUY';
          const time = new Date(log.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
          return `
            <tr>
              <td style="font-family:var(--font-mono)">${time}</td>
              <td>${log.symbol}</td>
              <td class="${isBuy ? 'badge-buy' : 'badge-sell'}">${log.order_type}</td>
              <td>${log.quantity}</td>
              <td class="badge-ok">${log.is_stub ? 'STUB' : 'LIVE'}</td>
            </tr>`;
        }).join('');
        
        state.ordersToday = data.logs.length;
        document.getElementById('ordersToday').textContent = state.ordersToday;
        if (data.logs[0]) {
           document.getElementById('lastOrder').textContent = `${data.logs[0].order_type} ${data.logs[0].symbol}`;
        }
      }
    }
  } catch (err) {
    console.error("Error fetching trade logs:", err);
  }
}

// ── Risk Gauges ───────────────────────────────────────────────────────────────
function updateRiskGauges() {
  const lossPct = Math.min(100, Math.abs(Math.min(state.dailyPnl, 0)) / 5000 * 100);
  const posPct  = Math.min(100, state.positions / 10 * 100);
  const opsPct  = Math.min(100, state.opsRate / 10 * 100);

  setGauge('lossGauge', lossPct);
  setGauge('posGauge',  posPct);
  setGauge('opsGauge',  opsPct);

  setText('lossUsed', '₹' + Math.abs(state.dailyPnl).toFixed(0));
  setText('posUsed',  state.positions + ' lots');
  setText('opsUsed',  state.opsRate.toFixed(1) + '/sec');
}

function setGauge(id, pct) {
  const el = document.getElementById(id);
  if (el) el.style.width = pct + '%';
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function updateOpsGauge(rate) {
  state.opsRate = rate;
  updateRiskGauges();
  setTimeout(() => { state.opsRate = 0; updateRiskGauges(); }, 2000);
}

function updatePnlDisplay() {
  const pnlEl = document.getElementById('pnlValue');
  if (!pnlEl) return;
  const v = state.dailyPnl;
  pnlEl.textContent = (v >= 0 ? '+₹' : '-₹') + Math.abs(v).toFixed(0);
  pnlEl.className   = 'pnl-value' + (v < 0 ? ' negative' : '');
  updateRiskGauges();
}

// ── Clock & Market Status ─────────────────────────────────────────────────────
function updateClock() {
  const now  = new Date();
  document.getElementById('clock').textContent = now.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  });

  // Session timer
  const elapsed = Math.floor((Date.now() - state.sessionStart) / 1000);
  const h = String(Math.floor(elapsed / 3600)).padStart(1, '0');
  const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
  const s = String(elapsed % 60).padStart(2, '0');
  setText('sessionTime', `Session: ${h}:${m}:${s}`);

  // Market status
  const h24  = now.getHours();
  const mins = now.getMinutes();
  const open = (h24 > 9 || (h24 === 9 && mins >= 15)) && (h24 < 15 || (h24 === 15 && mins <= 30));
  const badge = document.getElementById('marketBadge');
  const statusEl = document.getElementById('marketStatus');
  if (badge && statusEl) {
    statusEl.textContent = open ? 'NSE: OPEN' : 'NSE: CLOSED';
    badge.classList.toggle('closed', !open);
  }
}

// ── Timeframe ─────────────────────────────────────────────────────────────────
function setTimeframe(tf, btnEl) {
  state.timeframe = tf;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  loadSymbolData(state.symbol);
}

// ── Live news fetch ───────────────────────────────────────────────
async function fetchLiveNews() {
  try {
    const res = await fetch(`http://localhost:8000/api/news`);
    const data = await res.json();
    if (data.articles && data.articles.length > 0) {
       const articlesForUI = data.articles.map(a => ({
          headline: a.title,
          category: a.source || "Live News",
          published_at: a.published_at,
          sentiment: 0 // Assumed neutral
       }));
       if (typeof updateNewsTicker === 'function') updateNewsTicker(articlesForUI);
       if (typeof populateNewsPanel === 'function') populateNewsPanel(articlesForUI);
    }
  } catch (err) {
    console.error("Error fetching live news:", err);
  }
}

// ── Symbol change ─────────────────────────────────────────────────────────────
document.getElementById('symbolSelect')?.addEventListener('change', function() {
  loadSymbolData(this.value);
});

// ── Initialise ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  loadSymbolData('RELIANCE');
  updateClock();
  updateRiskGauges();
  fetchLiveNews();
  fetchTradeLogs();

  // Tick the clock every second
  setInterval(updateClock, 1000);

  // Poll real data and news every minute
  setInterval(() => {
    loadSymbolData(state.symbol);
    fetchLiveNews();
    fetchTradeLogs();
  }, 60000);

  // Periodically refresh chart
  setInterval(() => {
    try {
      if (candleChart) candleChart.update('none');
    } catch(e) {}
  }, 5000);
});
