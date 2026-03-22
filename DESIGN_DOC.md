# Design Document: StockMarket ADK — AI Trading Agent

The **StockMarket ADK** is a multi-agent autonomous trading system designed for the Indian Stock Market. It leverages the **Google Agent Development Kit (ADK)** and the **Gemini 2.0 Flash** model to perform sentiment analysis, technical research, risk validation, and order execution in a coordinated pipeline.

---

## 🏗️ System Architecture

The project follows a modular, service-oriented architecture:

### 1. **Core Backend (FastAPI)**
- **Role**: Serves as the central orchestrator and API gateway.
- **Components**:
    - `api/main.py`: Defines REST endpoints for the dashboard and manages ADK agent sessions.
    - `core/config.py`: Centralized settings management (Pydantic) for API keys and trading limits.
    - `core/database.py`: Asynchronous SQLite integration using SQLAlchemy.
    - `core/models.py`: Definitions for `TradeLog`, `SentimentAnalysis`, and `AuditLog`.

### 2. **AI Agents (Google ADK)**
The system uses a hierarchy of specialized agents:
- **SentimentAgent**: Scans macro news to determine market mood (BULLISH/BEARISH) and generates a watchlist of top 5 stocks.
- **AnalystAgent**: Performs technical analysis (RSI, MACD, Bollinger Bands) on specific symbols from the watchlist.
- **RiskAgent**: Validates proposed trades against SEBI rules and user-defined risk parameters (Max loss per day, position sizing).
- **ExecutionAgent**: Interfaces with broker tools to place and manage orders.
- **Parallel News Research Agents**:
    - `SectorNewsAgent`: Deep dive into industry-specific trends.
    - `GeopoliticalNewsAgent`: Analyzes global events impacting India.
    - NATIONAL_NEWS_AGENT: Focuses on Indian policy and domestic news.
    - `WorldNewsAgent`: Tracks global financial indices and cues.

### 3. **Skills & Tools (Python)**
Reusable logic injected into agents via ADK tools:
- `market_data`: Live/history fetching via yfinance (NSE: .NS).
- `technical_analysis`: Indicator calculations using NumPy (fallback) and pandas-ta.
- `news`: RSS and GNews intelligence gathering.
- `broker`: Order placement logic (Stub mode vs. Zerodha/Kite).
- `risk`: Mathematical validation of trade safety.

### 4. **Modern Dashboard (Vanilla JS)**
- **Role**: Premium UI for monitoring and manual intervention.
- **Tech Stack**: HTML5, Vanilla CSS (Glassmorphism), Chart.js (Candlesticks), Vanilla JS.
- **Features**: Live price charts, scrolling news ticker, real-time agent pipeline visualization, and a dedicated parallel research suite.

---

## 🔄 Agentic Workflow (The Pipeline)

1. **Macro Scan**: `SentimentAgent` gathers news -> computes sentiment score (0-100) -> identifies "Hot Sectors" -> picks stocks for the **Watchlist**.
2. **Deep Analysis**: For each stock in watchlist, `AnalystAgent` runs 3 technical indicators -> generates a combined `BUY/SELL/HOLD` signal.
3. **Safety Check**: `RiskAgent` inspects the signal -> checks current account P&L and SEBI limits -> Returns `APPROVED` or `BLOCKED`.
4. **Order Execution**: `ExecutionAgent` (if approved) places a limit/market order via the `broker_tools`.
5. **Persistence**: Every step (Agent internal thoughts, final decisions, trade logs) is stored in the **Audit Trail** in SQLite.

---

## 🛠️ Current Implementation Status

### ✅ Completed
- **Full Multi-Agent Pipeline**: Sentiment -> Analyst -> Risk -> Execution flow works.
- **Responsive Dashboard**: Beautiful Dark Mode UI with interactive charts.
- **Parallel Research**: 4 specialized agents can run concurrently via `Promise.allSettled()`.
- **Database Persistence**: All trades and sentiment scans are saved locally.
- **Rate-Limit Resiliency**: Session UUIDs and error handling for Gemini 429 errors.

### ⏳ Pending implementation
- **Live Broker Integration**: Currently in **Stub Mode**. Need to finish the OAuth flow for Kite/Dhan APIs to allow real money trading.
- **Live WebSocket Data**: Currently uses HTTP polling; should switch to Socket.io or WebSockets for Tick-by-Tick (TBT) data.
- **Advanced Indicators**: Add support for SuperTrend, Fibonacci levels, and Volume Profile.
- **Multi-Account Support**: Ability to manage multiple broker credentials simultaneously.
- **Cloud Deployment**: Containerization (Docker) and deployment to Google Cloud (Vertex AI).

---

## 🚦 Getting Started (Verification)

To run the whole system:
1. Ensure `.env` has your `GEMINI_API_KEY`.
2. Start the API server: `bash start_api.sh`.
3. Open `http://localhost:8000` in any browser.
4. Use the **Scan** or **Auto-Scan** buttons to trigger the AI agents.
