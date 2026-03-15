/**
 * sentiment.js
 * ─────────────
 * Simulates the SentimentAgent pipeline for the trading dashboard.
 *
 * In production, this would call the ADK backend via WebSocket/REST.
 * In demo/stub mode we generate realistic-looking sentiment from
 * a curated catalogue of geopolitical + market news scenarios.
 */

'use strict';

// ── Simulated News Catalogue ──────────────────────────────────────────────────
const NEWS_CATALOGUE = [
  // National
  { headline: "RBI holds repo rate; signals accommodative stance for Q1", category: "national", sectors: ["banking", "realty"], sentiment: 1 },
  { headline: "India GDP growth revised upward to 7.2% for FY26", category: "national", sectors: ["consumption", "infra"], sentiment: 1 },
  { headline: "India defense budget hiked 15% — HAL, BEL surge in pre-open", category: "national", sectors: ["defense"], sentiment: 1 },
  { headline: "India–China trade tensions rise; manufacturing stocks under pressure", category: "national", sectors: ["metal", "auto"], sentiment: -1 },
  { headline: "SEBI tightens F&O margin norms; derivatives volumes may drop", category: "national", sectors: ["banking"], sentiment: -1 },
  { headline: "India monsoon forecast ABOVE normal — FMCG, Agri stocks rally", category: "national", sectors: ["fmcg", "consumption"], sentiment: 1 },
  { headline: "PLI scheme expansion boosts pharma and EV manufacturing", category: "national", sectors: ["pharma", "auto"], sentiment: 1 },
  { headline: "India IT exports record $250B — sector premium intact", category: "national", sectors: ["it"], sentiment: 1 },

  // International
  { headline: "US Fed signals ONE rate cut in 2024 — dollar index falls", category: "international", sectors: ["it", "pharma"], sentiment: 1 },
  { headline: "US CPI cools; risk-on trade revives globally", category: "international", sectors: ["it", "banking", "realty"], sentiment: 1 },
  { headline: "US recession fears spike after weak jobs report", category: "international", sectors: ["it", "fmcg"], sentiment: -1 },
  { headline: "Nasdaq retreats on AI stock valuation concerns", category: "international", sectors: ["it"], sentiment: -1 },
  { headline: "China factory output contracts; iron ore prices fall", category: "international", sectors: ["metal"], sentiment: -1 },
  { headline: "Global shipping costs rise 40% on Red Sea disruptions", category: "international", sectors: ["auto", "fmcg", "metal"], sentiment: -1 },
  { headline: "OPEC+ cuts output by 1M bpd — crude spikes to $90", category: "international", sectors: ["energy"], sentiment: 1 },

  // Geopolitical
  { headline: "Russia-Ukraine ceasefire talks collapse; defense stocks globally rally", category: "geopolitical", sectors: ["defense", "energy"], sentiment: 1 },
  { headline: "Middle East tensions spike; oil surges 4% intraday", category: "geopolitical", sectors: ["energy", "defense"], sentiment: 1 },
  { headline: "US-China tariff war escalates; tech supply chains hit", category: "geopolitical", sectors: ["it", "auto", "metal"], sentiment: -1 },
  { headline: "Pakistan border skirmish raises India defense alert level", category: "geopolitical", sectors: ["defense", "telecom"], sentiment: 1 },
  { headline: "G20 commits to green energy — renewables and infra stocks gain", category: "geopolitical", sectors: ["infra", "energy"], sentiment: 1 },
];

// Sector → stock mapping (mirrors backend tools/news_tools.py)
const SECTOR_STOCKS = {
  it:          ["TCS", "INFY", "WIPRO"],
  banking:     ["HDFCBANK", "ICICIBANK", "SBIN"],
  energy:      ["RELIANCE", "ONGC"],
  defense:     ["HAL", "BEL"],
  pharma:      ["SUNPHARMA", "DRREDDY"],
  auto:        ["TATAMOTORS", "MARUTI"],
  fmcg:        ["HINDUNILVR", "ITC"],
  metal:       ["TATASTEEL", "JSWSTEEL"],
  realty:      ["DLF", "GODREJPROP"],
  telecom:     ["BHARTIARTL"],
  infra:       ["L&T", "ADANIPORTS"],
  consumption: ["TITAN", "DMART"],
};

// ── API Configuration ───────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000/api';

// ── Core Auto-Scan Logic ──────────────────────────────────────────────────────
async function triggerAutoScan() {
  const btn = document.getElementById('autoScanBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Scanning…';

  resetAllAgents();
  setAgentState('root', AgentState.RUNNING);

  // Step 1: SentimentAgent runs via API
  setAgentState('sentiment', AgentState.RUNNING);

  try {
    const res = await fetch(`${API_BASE}/scan/sentiment`, { method: 'POST' });
    const data = await res.json();
    const result = data.sentiment;

    displaySentimentBanner(result);
    updateSentimentAgentCard(result);
    // Transform themes/watchlist for the UI if needed
    if (result.themes && result.themes.length > 0) {
       populateNewsPanel(result.themes.map(t => ({headline: t, sentiment: result.sentiment_score >= 50 ? 1 : -1, category: "News", published_at: new Date().toISOString()})));
       updateNewsTicker(result.themes.map(t => ({headline: t, published_at: new Date().toISOString()})));
    }

    setAgentState('sentiment', AgentState.DONE);
    showToast('Sentiment Complete', `${result.market_sentiment} market · Watchlist ready`, 'success');

    // Step 2: Analyse the top stock from the watchlist sequentially via API
    // (To keep the demo fast, we'll just analyze the first 1-2 stocks)
    const scanCount = Math.min(2, result.watchlist.length);
    
    for (let i = 0; i < scanCount; i++) {
        const sym = result.watchlist[i];

        // Update the symbol selector so user sees what's being analysed
        const sel = document.getElementById('symbolSelect');
        if (sel && ![...sel.options].find(o => o.value === sym)) {
            const opt = document.createElement('option');
            opt.value = opt.textContent = sym;
            sel.appendChild(opt);
        }
        if (sel) sel.value = sym;

        // Optionally load the real chart data here if app.js is updated
        if (typeof loadSymbolData === 'function') loadSymbolData(sym);

        setAgentState('analyst', AgentState.RUNNING);

        const aRes = await fetch(`${API_BASE}/scan/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: sym })
        });
        const analystData = await aRes.json();
        const signal = analystData.signal;

        if (typeof updateAnalystStats === 'function') updateAnalystStats(signal);
        if (typeof addSignalFeedItem === 'function') addSignalFeedItem(signal);

        setAgentState('analyst', AgentState.DONE);

        // Step 3: Run Risk Check
        setAgentState('risk', AgentState.RUNNING);
        
        const rRes = await fetch(`${API_BASE}/scan/risk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: sym })
        });
        const riskData = await rRes.json();
        
        if (typeof updateRiskRules === 'function') updateRiskRules(riskData.rule_checks);
        setAgentState('risk', riskData.approved ? AgentState.DONE : AgentState.BLOCKED);

        if (riskData.approved) {
            if (typeof renderSignalBanner === 'function') renderSignalBanner(signal, true);
            showToast('Ready to Execute', `Best pick: ${sym} — ${signal.recommendation}`, 'success');
        } else {
            if (typeof renderSignalBanner === 'function') renderSignalBanner(signal, false);
            showToast('Risk Blocked', `${sym} blocked by SEBI rules`, 'error');
        }
        
        await new Promise(r => setTimeout(r, 1000));
    }
    
    setAgentState('root', AgentState.DONE);

  } catch (error) {
     console.error("Auto-Scan API Error:", error);
     showToast("API Error", "Failed to connect to backend", "error");
     setAgentState('root', AgentState.BLOCKED);
  } finally {
     btn.disabled = false;
     btn.innerHTML = '<span class="btn-icon">📰</span> Auto‑Scan';
  }
}

// ── Sentiment Simulation ──────────────────────────────────────────────────────
function runSentimentSimulation() {
  // Pick 6–9 random articles from catalogue
  const shuffled = [...NEWS_CATALOGUE].sort(() => Math.random() - 0.5);
  const articles  = shuffled.slice(0, 7);

  // Tally sentiment score
  let rawScore = 0;
  const sectorCount = {};
  articles.forEach(a => {
    rawScore += a.sentiment;
    (a.sectors || []).forEach(s => {
      sectorCount[s] = (sectorCount[s] || 0) + Math.abs(a.sentiment);
    });
  });

  // Score 0–100
  const sentiment_score = Math.max(10, Math.min(90, 50 + rawScore * 8));
  const market_sentiment = sentiment_score >= 58 ? 'BULLISH' : sentiment_score <= 42 ? 'BEARISH' : 'NEUTRAL';
  const macro_bias = sentiment_score >= 58 ? 'risk-on' : sentiment_score <= 42 ? 'risk-off' : 'neutral';

  // Top sectors
  const topSectors = Object.entries(sectorCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(e => e[0]);

  // Build watchlist (at least 5 stocks)
  const watchlist = [];
  topSectors.forEach(sec => {
    (SECTOR_STOCKS[sec] || []).slice(0, 2).forEach(sym => {
      if (!watchlist.includes(sym)) watchlist.push(sym);
    });
  });
  // Pad with defaults if needed
  const defaults = ['RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY'];
  defaults.forEach(s => { if (watchlist.length < 5 && !watchlist.includes(s)) watchlist.push(s); });

  // Key themes
  const themes = articles.slice(0, 3).map(a => a.headline.replace(/;.*/, '').slice(0, 60));
  const bestStockIndex = Math.floor(Math.random() * Math.min(3, watchlist.length));

  return { market_sentiment, sentiment_score, macro_bias, watchlist: watchlist.slice(0, 5), themes, articles, bestStockIndex };
}

// ── UI: Sentiment Banner ──────────────────────────────────────────────────────
function displaySentimentBanner(result) {
  const banner = document.getElementById('sentimentBanner');
  if (!banner) return;
  banner.style.display = 'flex';

  const moodEl = document.getElementById('sentimentMood');
  moodEl.textContent = result.market_sentiment;
  moodEl.className = 'sentiment-mood ' + result.market_sentiment.toLowerCase();

  document.getElementById('sentimentScoreFill').style.width = result.sentiment_score + '%';
  document.getElementById('sentimentScoreLabel').textContent = `${Math.round(result.sentiment_score)} / 100`;
  document.getElementById('sentimentBias').textContent = `Macro: ${result.macro_bias}`;

  document.getElementById('sentimentThemes').innerHTML = result.themes.map(t =>
    `<div class="theme-chip">• ${t}</div>`
  ).join('');

  document.getElementById('watchlistChips').innerHTML = result.watchlist.map((sym, i) =>
    `<span class="watchlist-chip ${i === result.bestStockIndex ? 'chip-star' : ''}" onclick="loadSymbolData('${sym}')">${i === result.bestStockIndex ? '⭐ ' : ''}${sym}</span>`
  ).join('');
}

// ── UI: SentimentAgent Card ───────────────────────────────────────────────────
function updateSentimentAgentCard(result) {
  const moodMap = { BULLISH: 'bullish', BEARISH: 'bearish', NEUTRAL: 'neutral' };
  const moodStat = document.getElementById('sentimentMoodStat');
  if (moodStat) {
    moodStat.textContent = result.market_sentiment;
    moodStat.className   = 'stat-value ' + (moodMap[result.market_sentiment] || 'neutral');
  }
  const scoreStat = document.getElementById('sentimentScoreStat');
  if (scoreStat) scoreStat.textContent = Math.round(result.sentiment_score) + ' / 100';

  const watchStat = document.getElementById('sentimentWatchStat');
  if (watchStat) watchStat.textContent = result.watchlist.join(', ');
}

// ── UI: News Panel (right sidebar) ───────────────────────────────────────────
function populateNewsPanel(articles) {
  const panel = document.getElementById('newsFeed');
  if (!panel) return;

  panel.innerHTML = articles.slice(0, 5).map(a => {
    const sign = a.sentiment > 0 ? 'positive' : a.sentiment < 0 ? 'negative' : 'neutral';
    const dot  = a.sentiment > 0 ? '🟢' : a.sentiment < 0 ? '🔴' : '🟡';
    const dateStr = a.published_at ? new Date(a.published_at).toLocaleString('en-IN', {day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit'}) : '';
    return `<div class="news-item ${sign}">
      <span class="news-dot">${dot}</span>
      <div>
        <div class="news-headline">${a.headline}</div>
        <div class="news-meta">${a.category.toUpperCase()} · ${dateStr}</div>
      </div>
    </div>`;
  }).join('');
}

// ── UI: News Ticker (scrolling) ───────────────────────────────────────────────
function updateNewsTicker(articles) {
  const content = document.getElementById('newsTickerContent');
  if (!content || !articles.length) return;
  content.textContent = articles.map(a => {
    const timeStr = a.published_at ? new Date(a.published_at).toLocaleTimeString('en-IN', {hour:'2-digit', minute:'2-digit'}) : '';
    return `${a.headline} (${timeStr})`;
  }).join('  ·  ');
}

// Extend agents.js to support SentimentAgent card
const _origReset = typeof resetAllAgents === 'function' ? resetAllAgents : null;
window.resetAllAgents = function() {
  if (_origReset) _origReset();
  setAgentState('sentiment', AgentState.IDLE);
};

// register the sentiment agent card in the agents map (injected after agents.js loads)
document.addEventListener('DOMContentLoaded', () => {
  // Extend agents map with sentiment
  if (typeof agents !== 'undefined') {
    agents.sentiment = { el: 'agentSentiment', badge: 'sentimentBadge', state: AgentState.IDLE };
  }
});
