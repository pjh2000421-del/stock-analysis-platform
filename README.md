# 한국 주식 AI 분석 플랫폼

한국 주식 중심의 금융 AI 분석 웹 플랫폼입니다. 단순 주가 조회를 넘어, 기업 가치·재무 상태·가격 흐름·뉴스·과거 유사 사건·시장 환경·머신러닝을 하나로 연결하여 "현재 기업 상태 분석 → 향후 시장 반응의 확률적 판단"을 지원합니다.

> 본 플랫폼은 "AI가 미래 주가를 정확히 맞힌다"고 주장하지 않습니다. 과거 사례와 통계, 머신러닝을 이용해 향후 시장 반응을 확률적으로 판단할 수 있도록 지원하는 것이 목표입니다. 모든 분석 결과는 투자 권유가 아니며 투자 결과를 보장하지 않습니다.

---

## 1. Architecture

```
Frontend (Next.js)
      ↓ REST API
Backend (FastAPI)
      ↓
Service Layer (services/)
      ↓
Provider(Adapter) / Database / ML
```

- Frontend와 Backend는 완전히 분리되어 있으며, UI 코드는 데이터 수집이나 ML을 직접 실행하지 않습니다.
- Backend는 `api → services → providers/db/ml` 순서로 계층이 분리되어 있고, 특정 데이터 공급자가 바뀌어도 Adapter만 교체하면 되도록 설계했습니다.
- 모든 종목의 데이터를 사전 저장하지 않고, 사용자가 검색한 기업 기준으로 **Lazy Loading + Caching**합니다. (DB 확인 → 없으면 외부 Provider 호출 → 저장 → 이후 재사용)

## 2. 폴더 구조

```
backend/
  app/
    api/routes/        # FastAPI 엔드포인트 (business logic 없음)
    core/               # 설정, 로깅, 공통 예외
    db/                 # DB 세션, 초기화
    models/             # SQLAlchemy 모델 (전체 스키마)
    schemas/            # Pydantic 요청/응답 스키마
    services/           # Lazy Loading/Caching 등 실제 business logic
    providers/          # 외부 API Adapter (주가/뉴스/재무/공시/거시)
    news_analysis/      # 감정분석(VADER), Event 추출
    event_analysis/     # 수익률/변동성, 유사도, 물가조정, Event Study
    valuation/          # Fundamental 지표 직접계산, DCF, 종합점수
    ml/                 # 전처리, STL, Lag, 검증(TimeSeriesSplit), 모델(BaseModel 등)
    simulation/          # Persona/인공시장 Mock 엔진
    config/             # 가중치 등 설정(JSON) - 하드코딩 금지
  tests/                # pytest 테스트
frontend/
  src/
    app/                # Next.js App Router 페이지
    components/         # UI 컴포넌트
    lib/                # API 클라이언트, i18n, 포맷 유틸
    types/              # TypeScript 타입 (백엔드 스키마 대응)
```

## 3. 환경설정

### 3-1. Backend 환경변수

```bash
cd backend
cp ../.env.example .env
# .env 파일을 열어 필요한 API Key를 채워 넣습니다.
```

| 변수 | 설명 | 없을 때 동작 |
|---|---|---|
| `DATABASE_URL` | 개발은 SQLite 기본값, 운영은 PostgreSQL/Supabase 연결문자열로 교체 | - |
| `DART_API_KEY` | OpenDART 재무제표/공시 조회 | 재무 데이터 "unavailable" 처리 |
| `NAVER_CLIENT_ID`/`SECRET` | 네이버 뉴스 검색 API | 뉴스 "unavailable" 처리 |
| `BIGKINDS_API_KEY` | 과거 뉴스(BIGKinds) | Provider unavailable로 정상 처리 (Mock 아님) |
| `KRX_OPEN_API_KEY`, `KOREA_INVESTMENT_*` | 공식 시세 API (선택) | 미설정 시 FinanceDataReader(무료, Key 불필요)로 자동 대체 |

### 3-2. Frontend 환경변수

```bash
cd frontend
cp .env.local.example .env.local
```

## 4. 실행 방법

### DB 생성

Backend 최초 실행 시 `app/main.py`의 startup 이벤트에서 자동으로 테이블을 생성합니다 (SQLite 기준). 수동 생성이 필요하면:

```bash
cd backend
python -m app.db.init_db
```

### Backend 실행

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API 문서: http://localhost:8000/docs

### Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

- http://localhost:3000

### 테스트 실행

```bash
cd backend
pytest
```

### ML 전처리 파이프라인 확인 (dummy dataset)

```bash
cd backend
pytest tests/test_ml_preprocessing.py -v
```

## 5. 데이터 공급자 (Provider)

| 데이터 | Provider | 비고 |
|---|---|---|
| 주가/거래량 | FinanceDataReader (기본, Key 불필요) | KRX Open API / 한국투자증권 API는 Adapter만 준비 (TODO) |
| 공시/재무제표 | OpenDART | corp_code 매핑을 최초 1회 캐싱 |
| 최신 뉴스 | 네이버 뉴스 검색 API | 본문 전체 저장 안 함 (제목/요약/URL/Event만 저장) |
| 과거 뉴스 | BIGKinds | 인증정보 없으면 "provider unavailable"로 정상 처리 (TODO: 승인 후 연동) |
| 시장지수/환율 | FinanceDataReader | KOSPI/KOSDAQ/USD-KRW |
| CPI(물가조정) | 한국은행 ECOS (TODO) | 미연동 시 물가조정 금액은 계산하지 않고 명목금액만 제공 |

모든 외부 데이터는 실패 시 전체 페이지를 깨뜨리지 않고, 사용자에게 이해 가능한 상태 메시지를 보여줍니다.

## 6. 현재 구현 상태

### 실제로 작동하는 기능 (Phase 1)
- 기업 검색 (기업명/종목코드), 종목 마스터 Lazy Bootstrap
- 주가/거래량 조회 + 캐싱, 기간별 차트(Candlestick + 거래량 + 뉴스 Event Marker)
- 뉴스 수집(네이버) + VADER 감정분석 + 규칙기반 Event Type 1차 분류
- 재무제표(OpenDART) 수집 + Fundamental 지표 직접 계산(PER/PBR/ROE/부채비율 등)
- 종합 점수(Valuation/Growth/Profitability/Financial Health) - config 기반 투명 가중치
- Simple View / Pro View
- DCF Calculator
- Watchlist 추가/삭제/목록
- 3개 언어(한국어/日本語/English) UI, locale별 숫자/날짜/통화 포맷

### 구조는 있지만 실제 데이터 연동/오케스트레이션이 TODO인 기능 (Phase 2 이후)
- 과거 유사 뉴스 검색·저장 파이프라인 (Similarity 계산 로직 자체는 구현/테스트 완료, DART Anchor + 후보 검색 오케스트레이션은 TODO)
- Event Study 자동 계산 (계산 함수는 구현/테스트 완료, 배치 연결 TODO)
- ML 예측 파이프라인 실제 학습/추론 연결 (BaseModel, 전처리, 검증 로직은 구현 및 테스트 완료)
- 뉴스 실시간 모니터링(Polling), Notification 생성 트리거
- Analysis Lab 실제 실행, Backtest 실제 계산
- Persona/Market Simulation은 Mock Adapter로만 동작 (PAMS 등 실제 엔진 연동 TODO)
- CPI 기반 물가조정 (ECOS 연동 TODO)

### Mock/Placeholder 명확 표시
- Market Simulation 결과는 `is_mock: true`로 명시
- AI 예측/백테스트는 미구현 상태를 `is_mock`/`is_available: false`로 명확히 반환 (가짜 수치를 보여주지 않음)

## 7. 알려진 한계

- **이 개발 환경에서는 `pip install` / `npm install`이 실행되지 않았습니다** (샌드박스의 외부 네트워크 정책상 PyPI/npm 레지스트리 접근이 차단됨). 따라서 `uvicorn` 실제 기동, `npm run build`, 외부 API 실호출은 이 환경에서 직접 검증하지 못했습니다. 코드는 Python 문법 검사(`py_compile`)와 TypeScript 구문 검사, 그리고 의존성이 필요 없는 순수 로직(수익률 계산, 재무지표 계산, Similarity, 종합점수, ML 전처리, TimeSeriesSplit 등 33개 테스트)은 실제로 실행하여 통과를 확인했습니다. 사용자 환경에서 `pip install -r requirements.txt` / `npm install` 실행 후 정상 동작 여부를 확인해 주세요.
- DART 계정과목 매핑(`account_nm`)은 기업/업종별로 표기가 다를 수 있어 일부 기업에서 재무 항목이 N/A로 나올 수 있습니다.
- 재무제표에 유동자산/유동부채/이자비용 등 세부 계정이 아직 매핑되지 않은 경우 유동비율/이자보상배율 등이 N/A로 표시됩니다.
- 네이버 뉴스 검색 API는 언론사명을 제공하지 않아 `source` 필드가 비어있을 수 있습니다.
- VADER는 영어 기반 lexicon이라 한국어 뉴스에는 정확도가 낮습니다 (요구사항에 따라 1단계로 우선 적용, `SentimentProvider` 추상화로 한국어 특화 모델 교체 가능).

## 8. 다음 Phase 제안

1. **Phase 2**: DART Anchor 기반 과거 유사 공시 탐색 오케스트레이션, 과거뉴스 후보 검색 → Similarity 계산 → 저장 파이프라인, Event Study 배치 연결
2. **Phase 3**: ML Feature Store 구축(Point-in-Time 준수), 실제 모델 학습/저장/캐시, SHAP 기반 Explainability, Auto Compare API
3. **Phase 4**: APScheduler 기반 Watchlist 뉴스 폴링, Notification 생성 트리거, Web Push
4. **Phase 5**: Analysis Lab 실제 실행 파이프라인 연결, Backtest 실제 계산
5. **Phase 6**: PAMS 등 실제 Agent-based Simulation 엔진 연동, LLM 기반 Persona 뉴스 해석

---

면책조항: 본 분석은 투자 권유가 아니며 투자 결과를 보장하지 않습니다.
