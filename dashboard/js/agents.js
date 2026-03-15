/**
 * agents.js
 * ─────────
 * Agent pipeline simulation for the trading dashboard.
 * Manages agent state transitions: IDLE → RUNNING → DONE / BLOCKED
 * Simulates the Analyst → Risk → Execution pipeline.
 */

'use strict';

// ── Agent State Machine ──────────────────────────────────────────────────────
const AgentState = { IDLE: 'IDLE', RUNNING: 'RUNNING', DONE: 'DONE', BLOCKED: 'BLOCKED' };

const agents = {
  root:     { el: 'agentRoot',     badge: 'rootBadge',     state: AgentState.IDLE },
  analyst:  { el: 'agentAnalyst',  badge: 'analystBadge',  state: AgentState.IDLE },
  risk:     { el: 'agentRisk',     badge: 'riskBadge',     state: AgentState.IDLE },
  execution:{ el: 'agentExecution',badge: 'execBadge',     state: AgentState.IDLE },
};

function setAgentState(name, state) {
  const agent = agents[name];
  if (!agent) return;
  agent.state = state;

  const card  = document.getElementById(agent.el);
  const badge = document.getElementById(agent.badge);
  if (!card || !badge) return;

  // Remove all state classes
  card.classList.remove('active', 'blocked');
  badge.className = 'agent-badge';

  switch (state) {
    case AgentState.RUNNING:
      card.classList.add('active');
      badge.classList.add('badge-running');
      badge.textContent = 'RUNNING';
      break;
    case AgentState.DONE:
      badge.classList.add('badge-done');
      badge.textContent = 'DONE';
      break;
    case AgentState.BLOCKED:
      card.classList.add('blocked');
      badge.classList.add('badge-blocked');
      badge.textContent = 'BLOCKED';
      break;
    default:
      badge.classList.add('badge-idle');
      badge.textContent = 'IDLE';
  }
}

function resetAllAgents() {
  Object.keys(agents).forEach(name => setAgentState(name, AgentState.IDLE));
  resetRiskRules();
}

// ── Risk Rule Display ─────────────────────────────────────────────────────────
const RISK_RULES = ['Daily Loss Limit', 'Position Limit', 'Market Hours', 'Order Validity'];

function resetRiskRules() {
  const container = document.getElementById('riskRules');
  if (!container) return;
  container.innerHTML = RISK_RULES.map(r =>
    `<div class="rule-row"><span class="rule-icon">○</span> ${r}</div>`
  ).join('');
}

function updateRiskRules(checks) {
  const container = document.getElementById('riskRules');
  if (!container || !checks) return;

  const ruleMap = {
    daily_loss_limit: 'Daily Loss Limit',
    position_limit:   'Position Limit',
    market_hours:     'Market Hours',
    quantity_check:   'Order Validity',
    order_type:       'Order Validity',
  };

  const results = {};
  checks.forEach(c => {
    const label = ruleMap[c.rule] || c.rule;
    results[label] = c.passed;
  });

  container.innerHTML = RISK_RULES.map(r => {
    const passed = results[r];
    const icon   = passed === true ? '✓' : (passed === false ? '✗' : '○');
    const cls    = passed === true ? 'pass' : (passed === false ? 'fail' : '');
    return `<div class="rule-row ${cls}"><span class="rule-icon">${icon}</span> ${r}</div>`;
  }).join('');
}

// ── Simulated Pipeline Runner ─────────────────────────────────────────────────
/**
 * Run a simulated agent pipeline for the given analysis result.
 * In production this is replaced by actual ADK streaming events.
 *
 * @param {object} signalData - Result from analyzeSymbol()
 * @param {number} dailyPnl   - Current day P&L for risk check
 * @param {number} positions  - Current open positions
 */
async function runAgentPipeline(signalData, dailyPnl = 0, positions = 0) {
  resetAllAgents();

  // ── Step 1: Root starts ───────────────────────────────────────
  setAgentState('root', AgentState.RUNNING);
  await sleep(600);

  // ── Step 2: Analyst runs ──────────────────────────────────────
  setAgentState('root',    AgentState.DONE);
  setAgentState('analyst', AgentState.RUNNING);

  // Simulate analyst fetching data
  await sleep(1200);
  updateAnalystStats(signalData);
  setAgentState('analyst', AgentState.DONE);

  // ── Step 3: Risk validates ────────────────────────────────────
  setAgentState('risk', AgentState.RUNNING);
  await sleep(900);

  const approved = simulateRiskCheck(dailyPnl, positions);
  const fakeChecks = buildFakeChecks(approved, dailyPnl, positions);
  updateRiskRules(fakeChecks);
  setAgentState('risk', approved ? AgentState.DONE : AgentState.BLOCKED);

  if (!approved) {
    showToast('Risk Blocked', 'Trade rejected by SEBI risk rules.', 'error');
    return { approved: false };
  }

  // ── Step 4: Execution (only if approved & BUY/SELL signal) ───
  if (signalData.recommendation !== 'HOLD') {
    setAgentState('execution', AgentState.RUNNING);
    await sleep(700);
    setAgentState('execution', AgentState.DONE);
    return { approved: true, executed: true };
  }

  return { approved: true, executed: false };
}

// ── Stats Updaters ────────────────────────────────────────────────────────────
function updateAnalystStats(signal) {
  if (!signal) return;

  const rsi  = signal.rsi?.rsi;
  const macd = signal.macd?.crossover_signal;
  const bb   = signal.bollinger?.signal;

  setStatValue('rsiValue',  rsi != null ? `${rsi} (${signal.rsi?.signal || ''})` : '—', signal.rsi?.signal);
  setStatValue('macdValue', macd ? macd.replace(/_/g, ' ').toUpperCase() : '—', macd?.includes('bullish') ? 'bullish' : 'bearish');
  setStatValue('bbValue',   bb   ? bb.replace(/_/g, ' ')   : '—', bb?.includes('oversold') ? 'bullish' : (bb?.includes('overbought') ? 'bearish' : 'neutral'));
}

function setStatValue(id, text, signal) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = 'stat-value' + (signal === 'bullish' || signal === 'oversold' ? ' bullish' : signal === 'bearish' || signal === 'overbought' ? ' bearish' : ' neutral');
}

// ── Risk Simulation Helpers ───────────────────────────────────────────────────
function simulateRiskCheck(dailyPnl, positions) {
  const maxLoss = -5000;
  const maxPos  = 10;
  const now     = new Date();
  const h = now.getHours(), m = now.getMinutes();
  const isMarketHours = (h > 9 || (h === 9 && m >= 15)) && (h < 15 || (h === 15 && m <= 30));
  return dailyPnl > maxLoss && positions < maxPos && isMarketHours;
}

function buildFakeChecks(approved, dailyPnl, positions) {
  const now   = new Date();
  const h = now.getHours(), m = now.getMinutes();
  const marketOpen = (h > 9 || (h === 9 && m >= 15)) && (h < 15 || (h === 15 && m <= 30));
  return [
    { rule: 'daily_loss_limit', passed: dailyPnl > -5000 },
    { rule: 'position_limit',   passed: positions < 10 },
    { rule: 'market_hours',     passed: marketOpen },
    { rule: 'quantity_check',   passed: true },
    { rule: 'order_type',       passed: true },
  ];
}

// ── Utility ───────────────────────────────────────────────────────────────────
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Toast notification system
function showToast(title, message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons = { success: '✅', error: '🚫', warning: '⚠️' };
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
