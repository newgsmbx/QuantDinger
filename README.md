<div align="center">
  <img src="https://ai.quantdinger.com/img/logo.e0f510a8.png" alt="QuantDinger" width="160" />
  <h2>QuantDinger</h2>
  <p>
    A local-first quant research & trading workspace: market data, indicators, AI analysis, backtesting, and strategy execution in one place.
  </p>
  <p>
    <a href="https://www.quantdinger.com">Website</a>
    ·
    <a href="https://ai.quantdinger.com">Live Demo</a>
  </p>
  <p>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" /></a>
    <img alt="Backend" src="https://img.shields.io/badge/Backend-Flask%20%2B%20SQLite-black" />
    <img alt="Frontend" src="https://img.shields.io/badge/Frontend-Vue%202%20%2B%20Ant%20Design%20Vue-2c7be5" />
    <a href="https://ai.quantdinger.com"><img alt="Demo" src="https://img.shields.io/badge/Demo-ai.quantdinger.com-00b894" /></a>
  </p>
</div>

---

This repository is intentionally simple (no PHP gateway): it contains **one Python backend** and **one web UI**.

- **`backend_api_python/`**: Flask API + strategy runtime + AI agents
- **`quantdinger_vue/`**: Vue 2 UI (Ant Design Vue based) with charts, backtests, and strategy management

> This repo does not include real secrets. Configure API keys and credentials via `.env` / environment variables.

---

### Why QuantDinger

- **Local-first (SQLite) out of the box**: no external database required to run a full workflow locally.
- **AI research team in code**: multi-agent analysis produces structured reports (with optional web search + LLMs).
- **Multi-market data layer**: a factory-based data source abstraction for crypto, US stocks, CN/HK stocks, forex, and futures.
- **From signals to execution**: strategy runtime + a pending-order worker to dispatch queued actions reliably.

---

### Highlights (What You Get)

- **Multi-market market data**
  - Data source factory in `backend_api_python/app/data_sources/`.
  - Optional proxy support for restricted networks (see `.env`).

- **AI multi-agent analysis**
  - Coordinator + role agents in `backend_api_python/app/services/agents/`.
  - Optional web search (Google/Bing) and LLM access (OpenRouter).

- **Indicator engine + backtesting**
  - Indicator code storage with safe execution utilities.
  - Backtest endpoints + persisted run history (SQLite).

- **Strategy runtime**
  - Thread-based executor with startup auto-restore (configurable).
  - Background pending-order worker that polls queued orders and dispatches signals (can be disabled).

- **Live trading integrations**
  - Exchange execution adapters in `backend_api_python/app/services/live_trading/` (CCXT-based where applicable).

- **Local auth (single-user)**
  - Simple login (`/login`) with env-configured admin credentials (JWT token).

---

### Architecture (Current Repo)

```text
┌─────────────────────────────┐
│      quantdinger_vue         │
│   (Vue 2 + Ant Design Vue)   │
└──────────────┬──────────────┘
               │  HTTP (/api/*)
               ▼
┌─────────────────────────────┐
│     backend_api_python       │
│   (Flask + strategy runtime) │
└──────────────┬──────────────┘
               │
               ├─ SQLite (quantdinger.db)
               ├─ Redis (optional cache)
               └─ Data providers / LLMs / Exchanges
```

---

### Repository Layout

```text
.
├─ backend_api_python/         # Flask API + AI + backtest + strategy runtime
│  ├─ app/
│  ├─ env.example              # Copy to .env for local config
│  ├─ requirements.txt
│  └─ run.py                   # Entrypoint
└─ quantdinger_vue/            # Vue 2 UI (dev server proxies /api -> backend)
```

---

### Quick Start (Local Development)

**Prerequisites**

- Python 3.10+ recommended
- Node.js 16+ recommended

#### 1) Start the backend (Flask API)

```bash
cd backend_api_python
pip install -r requirements.txt
copy env.example .env   # Windows PowerShell users can use: Copy-Item env.example .env
python run.py
```

Backend will be available at `http://localhost:5000`.

#### 2) Start the frontend (Vue UI)

```bash
cd quantdinger_vue
npm install
npm run serve
```

Frontend dev server runs at `http://localhost:8000` and proxies `/api/*` to `http://localhost:5000` (see `quantdinger_vue/vue.config.js`).

---

### Configuration (.env)

Use `backend_api_python/env.example` as a template. Common settings include:

- **Auth**: `SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD`
- **Server**: `PYTHON_API_HOST`, `PYTHON_API_PORT`, `PYTHON_API_DEBUG`
- **Database**: `SQLITE_DATABASE_FILE` (optional; default is `backend_api_python/quantdinger.db`)
- **AI / LLM**: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, timeouts
- **Web search**: `SEARCH_PROVIDER`, `SEARCH_GOOGLE_*`, `SEARCH_BING_API_KEY`
- **Proxy (optional)**: `PROXY_PORT` or `PROXY_URL`
- **Workers**: `ENABLE_PENDING_ORDER_WORKER`, `DISABLE_RESTORE_RUNNING_STRATEGIES`

---

### API

The backend provides REST endpoints for login, market data, indicators, backtesting, strategies, and AI analysis.

- Health: `GET /health`
- Auth: `POST /login`, `POST /logout`, `GET /info`

For the full route list, see `backend_api_python/app/routes/`.

---

### License

Licensed under the **Apache License 2.0**. See `LICENSE`.

---

### Acknowledgements

QuantDinger stands on the shoulders of great open-source projects, including:

- **Flask** / **flask-cors**
- **Pandas**
- **CCXT**
- **yfinance**, **akshare**, **requests**
- **Vue 2** and **Ant Design Vue**
- Charting libraries used in the UI (e.g., **KlineCharts**)

Thanks to maintainers and contributors across these ecosystems.


