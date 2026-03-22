/**
 * news_research.js
 * ────────────────
 * Logic for the Parallel News Research Dashboard.
 * Triggers multiple ADK agents in parallel and renders their findings.
 */

'use strict';

const API_BASE = 'http://localhost:8000/api';

const AgentState = {
  IDLE: 'IDLE',
  RUNNING: 'RUNNING',
  DONE: 'DONE',
  BLOCKED: 'BLOCKED'
};

const agents = {
  sector:   { el: 'agentSector', badge: 'sectorBadge', state: AgentState.IDLE, endpoint: '/news_research/sector' },
  geo:      { el: 'agentGeo', badge: 'geoBadge', state: AgentState.IDLE, endpoint: '/news_research/geopolitical' },
  national: { el: 'agentNational', badge: 'nationalBadge', state: AgentState.IDLE, endpoint: '/news_research/national' },
  world:    { el: 'agentWorld', badge: 'worldBadge', state: AgentState.IDLE, endpoint: '/news_research/world' }
};

function setAgentState(id, state) {
  const agent = agents[id];
  if (!agent) return;
  agent.state = state;
  const badge = document.getElementById(agent.badge);
  const card  = document.getElementById(agent.el);
  
  badge.textContent = state;
  badge.className = 'agent-badge ' + (state === AgentState.IDLE ? 'badge-idle' : state === AgentState.RUNNING ? 'badge-running' : state === AgentState.DONE ? 'badge-done' : 'badge-blocked');
  
  if (state === AgentState.RUNNING) card.classList.add('agent-running');
  else card.classList.remove('agent-running');
}

async function startParallelResearch() {
  const btn = document.getElementById('startResearchBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> Researching...';
  
  const feed = document.getElementById('researchFeed');
  feed.innerHTML = ''; // Clear previous

  // Bug 6 fix: run all 4 agents truly in parallel using Promise.allSettled
  // Each agent fires its API call at the same time; results are rendered as they arrive.
  const agentKeys = Object.keys(agents);

  // Mark all agents as RUNNING immediately to give the correct parallel visual
  agentKeys.forEach(key => setAgentState(key, AgentState.RUNNING));

  // Fire all requests concurrently and wait for all to settle
  const results = await Promise.allSettled(
    agentKeys.map(key => runAgentResearch(key))
  );

  const failed = results.filter(r => r.status === 'rejected').length;
  if (failed === 0) {
    showToast('Research Complete', 'All 4 agents finished their parallel analysis.', 'success');
  } else {
    showToast('Research Partial', `${agentKeys.length - failed} of ${agentKeys.length} agents succeeded.`, 'warning');
  }

  btn.disabled = false;
  btn.innerHTML = '<span class="btn-icon">🚀</span> Start Parallel Research';
}

async function runAgentResearch(key) {
  // Note: state is already set to RUNNING by startParallelResearch before this fires
  const agent = agents[key];
  
  try {
    const res = await fetch(`${API_BASE}${agent.endpoint}`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text().catch(() => '')}`);
    const data = await res.json();
    
    setAgentState(key, AgentState.DONE);
    renderResearchResult(key, data.research || '(No content returned)');
    
  } catch (err) {
    console.error(`Research error for ${key}:`, err);
    setAgentState(key, AgentState.BLOCKED);
    showToast('Agent Error', `${key.toUpperCase()}: ${err.message}`, 'error');
    throw err; // re-throw so Promise.allSettled gets the rejection
  }
}

function renderResearchResult(type, content) {
  const feed = document.getElementById('researchFeed');
  const card = document.createElement('div');
  card.className = `research-card ${type}`;
  
  // Extract symbols from content (simple heuristic for UI display)
  const symbols = content.match(/\b[A-Z]{3,10}\b/g) || [];
  const uniqueSymbols = [...new Set(symbols)].filter(s => !['NSE', 'BSE', 'RBI', 'USD', 'INR', 'FED'].includes(s)).slice(0, 5);
  
  card.innerHTML = `
    <div class="research-header">
      <span class="agent-tag">${type} Agent</span>
      <span style="font-size:0.7rem; color:var(--text-dim)">Just now</span>
    </div>
    <div class="research-content" style="white-space: pre-line; font-size: 0.9rem; line-height: 1.5;">
      ${formatContent(content)}
    </div>
    <div class="impact-list">
      ${uniqueSymbols.map(s => `<span class="impact-chip">${s}</span>`).join('')}
    </div>
  `;
  
  feed.prepend(card);
}

function formatContent(text) {
  if (typeof marked !== 'undefined') {
    return marked.parse(text);
  }
  // Advanced regex fallback if CDN is blocked/offline
  let html = text;
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
  // Handle lists
  html = html.replace(/^\* (.*$)/gim, '<li>$1</li>');
  html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
  
  // Clean up newlines, preserving them as breaks where needed
  html = html.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
  // Remove breaks immediately following a heading or list
  html = html.replace(/<\/h3><br>/g, '</h3>').replace(/<\/h2><br>/g, '</h2>').replace(/<\/ul><br>/g, '</ul>');
  return html;
}

// Toast notification system
function showToast(title, message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) {
    console.warn('Toast container not found, falling back to alert');
    alert(`${title}: ${message}`);
    return;
  }

  const icons = { success: '✅', error: '🚫', warning: '⚠️', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || '💬'}</span>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      <div class="toast-msg">${message}</div>
    </div>`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 350);
  }, 4000);
}
