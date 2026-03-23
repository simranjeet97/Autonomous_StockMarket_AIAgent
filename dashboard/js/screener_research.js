/**
 * screener_research.js
 * ─────────
 * Handles frontend logic for the Screener Research page.
 * Sends natural language queries to backend, displays translated query and ranked table.
 */

async function submitScreenerQuery() {
    const queryInput = document.getElementById('userQuery').value.trim();
    if (!queryInput) {
        showToast('Error', 'Please enter a query.', 'error');
        return;
    }
    
    // UI state: loading
    const btn = document.getElementById('runResearchBtn');
    const spinner = document.getElementById('loadingSpinner');
    const queryDisplay = document.getElementById('screener-query-display');
    const tbody = document.getElementById('screener-results-body');
    
    btn.disabled = true;
    btn.innerHTML = 'Running...';
    spinner.style.display = 'inline-block';
    
    queryDisplay.textContent = 'Translating query and scraping Screener.in... (This may take a moment)';
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 40px 0;">Agent is scraping and enriching data...</td></tr>`;
    
    try {
        await runScreenerResearch(queryInput);
    } catch (error) {
        console.error("Screener API error:", error);
        showToast('Error', 'Failed to run Screener Research.', 'error');
        queryDisplay.textContent = 'Error occurred.';
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--neon-red); padding: 40px 0;">Error analyzing stocks. Check backend logs.</td></tr>`;
    } finally {
        // UI state: restore
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">⚡</span> Analyze Stocks';
        spinner.style.display = 'none';
    }
}

async function runScreenerResearch(query) {
    // Requires view transitions enabled in modern browsers
    if (!document.startViewTransition) {
        await executeScreenerRender(query);
    } else {
        await document.startViewTransition(async () => {
             await executeScreenerRender(query);
        }).updateCallbackDone;
    }
}

async function executeScreenerRender(query) {
    const res = await fetch('/screener/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ query })
    });
    
    if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
    }
    
    const data = await res.json();
    
    // Show the translated query
    document.getElementById('screener-query-display').textContent = data.screener_query || 'Unknown Output';
    
    // Render ranked table
    const tbody = document.getElementById('screener-results-body');
    tbody.innerHTML = '';
    
    if (!data.results || data.results.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 40px 0;">No stocks found matching the criteria.</td></tr>`;
        return;
    }
    
    data.results.forEach(stock => {
        // Style score
        let scoreClass = 'score-med';
        if (stock.investment_score >= 80) scoreClass = 'score-high';
        else if (stock.investment_score < 50) scoreClass = 'score-low';
            
        const row = `<tr>
            <td>${stock.rank || '-'}</td>
            <td><strong>${stock.ticker || 'N/A'}</strong></td>
            <td class="${scoreClass}">${stock.investment_score || 0}/100</td>
            <td>${stock.allocation_pct || 0}%</td>
            <td style="color: var(--text-secondary); line-height: 1.4;">${stock.rationale || ''}</td>
        </tr>`;
        tbody.insertAdjacentHTML('beforeend', row);
    });
    
    showToast('Success', 'Stock screening and ranking completed.', 'success');
}

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
