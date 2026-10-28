# Korean Equity Analysis Platform

[한국어 README](README.ko.md)

A full-stack web platform for analyzing Korean listed companies. It brings stock prices, financial statements, regulatory disclosures and news into one company view, then layers valuation, news sentiment and machine-learning analysis on top.

The goal is not to "predict stock prices." The platform helps users judge likely market reactions **probabilistically**, using historical data, statistics and models, and it shows how reliable each signal has been in the past.

> Disclaimer: Nothing on this platform is investment advice, and no result guarantees future returns.

---

## Features

**Company analysis**
- Company search by name or ticker, with lazy loading of the KRX stock master list
- Price and volume charts (candlestick + volume) with news event markers; markers show a one-word event label, with full headlines on hover
- Financial statements from OpenDART, with fundamentals computed in-house (PER, PBR, ROE, debt ratio and more)
- Composite score across valuation, growth, profitability and financial health, with weights kept in config files rather than hard-coded
- Peer comparison within the same industry classification
- DCF calculator with WACC estimated from the company's beta against the KOSPI index
- Inflation adjustment of historical amounts using CPI from the Bank of Korea (ECOS)
- AI Q&A panel on the company page (Anthropic Claude API)

**News analysis**
- News collection with a three-tier provider chain (Naver News → NewsData.io → GNews)
- Korean financial-news sentiment with KR-FinBERT-SC (`snunlp/KR-FinBert-SC`), with VADER as the fallback for English articles or when the model is unavailable
- Rule-based event classification (supply contract, earnings, M&A, capital increase, …)
- Importance scoring that extracts monetary amounts from headlines (e.g. "1조 2000억원") and scales them against market cap, with extra weight for events confirmed by a DART disclosure or covered by several outlets

**Analysis Lab (machine learning)**
- Features: price, volume, news sentiment, news frequency and event type, plus moving averages and lag features
- Models: linear regression, logistic regression, random forest, XGBoost (regression only), ANN and LSTM (optional, require TensorFlow), and an Auto Compare mode that runs several models at once
- Results shown as backtest-based confidence levels (Low / Medium / High) instead of raw predictions

**User experience**
- Simple View for beginners and Pro View for experienced users
- Watchlist
- Three UI languages (Japanese, English, Korean), with locale-specific number, date and currency formats

## Architecture

```
Frontend (Next.js, TypeScript)
        │  REST API
        ▼
Backend (FastAPI)
  api/routes   →  thin HTTP layer, no business logic
  services/    →  business logic, lazy loading and caching
  providers/   →  adapters for external data sources
  db / ml      →  SQLAlchemy models, ML pipeline
```

- **Layered backend.** Each external source sits behind a provider adapter, so a data source can be replaced without touching the services.
- **Lazy loading + caching.** Data is not preloaded for every stock. When a user opens a company, the backend checks the database first, calls the external provider only if needed, stores the result and reuses it.
- **Graceful degradation.** A failing or missing data source never breaks the whole page. Each provider returns an explicit `ok` / `unavailable` / `error` status, and the UI shows a readable message instead.
- **Fallback chains.** When the primary KRX listing endpoint was blocked in production, the stock master list falls back step by step to KRX-DESC, then the OpenDART corporate-code list, then a bundled static list. Diagnostic endpoints report which source succeeded.
- **No fake numbers.** Features that are not finished return `is_available: false` or `is_mock: true` rather than invented results.

## Machine-learning validation

Stock data is a time series, so random train/test splits would leak future information into training. The pipeline avoids this in three ways:

1. **Chronological splits.** `TimeSeriesSplit` with 5 folds (train on the past, test on the following period), or walk-forward validation that grows the training window step by step.
2. **Scaling fitted on training data only.** In every fold, the MinMax scaler is fitted on the training slice and only applied to the test slice.
3. **Metrics averaged across folds.** Regression: MAE, RMSE, R² and directional accuracy. Classification: accuracy, precision, recall, F1 and ROC-AUC.

The final prediction comes from a model retrained on all available data. The confidence level shown next to it reflects how well that model and feature combination performed across the historical folds.

Guards added after testing:
- A regression-only model (XGBoost, ANN) can no longer be selected for a classification target. Before the fix it silently returned meaningless values.
- Unsupported features or targets, and data ranges that are too short, fail with a clear message instead of a server error.

## Tech stack

| Area | Tools |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | SQLite (development), PostgreSQL (production) |
| Data | pandas, NumPy, FinanceDataReader, OpenDART, Naver News API, ECOS |
| ML / NLP | scikit-learn, XGBoost, statsmodels, Hugging Face Transformers (KR-FinBERT-SC), VADER |
| Frontend | Next.js 14, React, TypeScript, Tailwind CSS, Lightweight Charts, Recharts |
| Testing | pytest (51 tests) |
| Deployment | Render |

## Getting started

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env            # then fill in the API keys you have
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

Tables are created automatically on first start (SQLite). Schema changes are managed with Alembic; see [backend/alembic/README.md](backend/alembic/README.md).

### 2. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

App: http://localhost:3000

### 3. Tests

```bash
cd backend
pytest
```

External providers are replaced with mocks, so the tests run without network access or API keys.

### Environment variables

Every key is optional. A missing key turns only the matching feature into an "unavailable" state.

| Variable | Used for |
| --- | --- |
| `DATABASE_URL` | SQLite by default; a PostgreSQL connection string in production |
| `DART_API_KEY` | Financial statements and disclosures (OpenDART) |
| `ECOS_API_KEY` | CPI for inflation adjustment (Bank of Korea) |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | Primary news source (Naver API Hub) |
| `NEWSDATA_API_KEY`, `GNEWS_API_KEY` | Secondary and tertiary news sources |
| `ANTHROPIC_API_KEY` | AI Q&A panel |
| `KRX_OPEN_API_KEY`, `KOREA_INVESTMENT_*` | Official price APIs (adapters prepared; FinanceDataReader is the default) |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend → backend address |

## Project structure

```
backend/
  app/
    api/routes/       FastAPI endpoints
    core/             settings, logging, errors
    db/               session and initialization
    models/           SQLAlchemy models
    schemas/          Pydantic request/response schemas
    services/         business logic
    providers/        external data adapters (prices, news, financials, disclosures, macro, LLM)
    news_analysis/    sentiment, event extraction, de-duplication
    event_analysis/   returns, volatility, similarity, inflation adjustment, event study
    valuation/        fundamentals, DCF, WACC, composite score
    ml/               features, preprocessing, validation, models, pipeline
    simulation/       persona-based market simulation (mock)
    config/           scoring and similarity weights (JSON)
  alembic/            database migrations
  tests/              pytest
frontend/
  src/
    app/              Next.js pages (company, search, watchlist, analysis lab, simulation lab)
    components/       UI components
    lib/              API client, i18n, formatting
    types/            TypeScript types matching the backend schemas
```

## Status and roadmap

Not finished yet, and labeled as such in the API and UI:

- Search for similar past news and its price-reaction statistics (the similarity calculation is implemented and tested; the search and storage pipeline is not)
- Trading-strategy backtest (win rate, cumulative return, Sharpe ratio, maximum drawdown)
- Background news polling and watchlist notifications
- Agent-based market simulation (currently a mock)
- Explainability for model predictions (SHAP)

Known limitations:

- DART account names vary by company and industry, so some financial items may show as N/A.
- The Naver News API does not return the publisher name or view counts.
- Short-term price direction is hard to predict. In testing, a 5-day return model for Samsung Electronics reached only 38% directional accuracy and was correctly labeled "Low" confidence.

---

Built by Junhong Park with AI-assisted development (Claude).
