# ⚡ StockMarket ADK — AI Trading Agent

Production-ready multi-agent trading system for NSE/Nifty 50 built with **Google Agent Development Kit (ADK)** and **Gemini 3.0 Flash**.

---

## 🏗️ Project Structure

```
StockMarket_ADK/
├── trading_agent/          # ADK entry-point (adk web .)
│   ├── __init__.py
│   └── agent.py            # TradingRoot orchestrator
├── agents/
│   ├── analyst_agent.py    # RSI / MACD / Bollinger specialist
│   ├── risk_agent.py       # SEBI 2026 compliance guardian
│   └── execution_agent.py  # Order placement (limit orders)
├── tools/
│   ├── broker_tools.py     # Zerodha Kite wrapper (stub-safe)

│   ├── market_data_tools.py# LTP / OHLC via yfinance
│   ├── risk_tools.py       # Hard-gate validate_risk()
│   └── technical_analysis_tools.py  # RSI, MACD, Bollinger
├── core/
│   ├── config.py           # Pydantic settings + .env
│   ├── order_throttle.py   # ≤10 OPS token bucket
│   └── session_manager.py  # ADK session state helpers
├── dashboard/              # Standalone trading UI
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── app.js          # Charts + state
│       └── agents.js       # Pipeline animation
├── .env.example
├── requirements.txt
└── pyproject.toml
```

---

## 🚀 Quick Start

### 1. Setup Environment
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env — add your GOOGLE_API_KEY (AI Studio)
```

### 3. Run ADK Web UI
```bash
adk web .
# Open http://localhost:8080
# Select "TradingRoot" from the agent dropdown
```

### 4. Open Dashboard
```bash
open dashboard/index.html        # macOS
# Or double-click dashboard/index.html in Finder
```

---

## 🤖 Agent Pipeline

```
User Goal
  │
  ▼
TradingRoot (Orchestrator)
  │
  ├──► AnalystAgent  →  RSI + MACD + Bollinger Bands  →  BUY/SELL/HOLD
  │
  ├──► RiskAgent     →  validate_risk() hard gate      →  APPROVED / BLOCKED
  │                        ✓ Daily loss ≤ ₹5,000
  │                        ✓ Positions ≤ 10 lots
  │                        ✓ Market hours (09:15–15:30)
  │                        ✓ Quantity & order type valid
  │
  └──► ExecutionAgent (only if user approves)
           └──► place_nifty_order() via Zerodha Kite API
                └──► OrderThrottle (≤10 OPS — SEBI retail)
```

---

## 🛡️ SEBI 2026 Compliance

| Feature | Implementation |
|---------|---------------|
| Hard-gate risk | `validate_risk()` returns `bool` — non-negotiable |
| OPS throttle | Token-bucket `≤10 orders/sec` |
| Intraday only | Default `product='INTRADAY'` — no overnight |
| Limit orders only | ExecutionAgent instruction enforces this |
| Daily loss limit | ₹5,000 max drawdown enforced by RiskAgent |

---

## 🔧 Configuration (`.env`)

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | AI Studio key for Gemini 2.0 Flash |
| `KITE_API_KEY` / `KITE_API_SECRET` | Zerodha broker credentials |
| `DB_URL` | SQLite connection string (default: trading.db) |
| `MAX_DAILY_LOSS_INR` | Default: ₹5,000 |

| `MAX_POSITION_LOTS` | Default: 10 |
| `MAX_ORDERS_PER_SECOND` | Default: 10 (SEBI retail) |

---

## 📊 Dashboard Features

- **Dark glassmorphism** design with neon green accents
- **Candlestick chart** (Chart.js financial) with volume bars
- **Agent pipeline** status cards with live animation
- **Risk gauges** — loss utilization, position %, OPS meter
- **Signal feed** — real-time BUY/SELL/HOLD log
- **Trade log** — tabular order history

---

## 🗺️ Roadmap

- [x] Connect real news via GNews API
- [x] SQLite integration for local trade persistence
- [x] Zerodha (Kite) broker support
- [ ] Websocket streaming for real-time OHLC
- [ ] Vertex AI Agent Engine deployment

