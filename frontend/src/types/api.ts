/** 백엔드 Pydantic 스키마와 대응하는 TypeScript 타입 정의. */

/** 투자용 산업분류 (WICS 등). industry가 실제로 화면에 표시할 "업종"이다. */
export interface ClassificationOut {
  sector: string | null;
  industry: string | null;
  sub_industry: string | null;
  system: string | null;
  source: string | null;
  confidence: number | null;
  updated_at: string | null;
}

/** KRX 상장법인목록(KSIC) 기반 원본 분류. 투자분석용이 아니라 보조 참고용. */
export interface RawClassificationOut {
  industry: string | null;
  source: string;
}

export interface CompanySearchResult {
  ticker: string;
  company_name: string;
  market: string | null;
  sector: string | null;
  industry: string | null;
  investment_industry: string | null;
}

export interface CompanySearchResponse {
  query: string;
  results: CompanySearchResult[];
}

export interface CompanyDetail {
  ticker: string;
  company_name: string;
  company_name_en: string | null;
  market: string | null;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  classification: ClassificationOut | null;
  raw_classification: RawClassificationOut | null;
  current_price: number | null;
  price_change: number | null;
  price_change_pct: number | null;
  price_date: string | null;
  last_updated: string | null;
}

export interface PricePoint {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface EventMarker {
  date: string;
  news_id: number;
  title: string;
  event_type: string | null;
}

export interface PriceHistoryResponse {
  ticker: string;
  period: string;
  prices: PricePoint[];
  event_markers: EventMarker[];
}

export interface NewsItem {
  id: number;
  title: string;
  summary: string | null;
  source: string | null;
  published_at: string | null;
  url: string;
  sentiment_score: number | null;
  importance_score: number | null;
  event_type: string | null;
  event_subtype: string | null;
  is_mock: boolean;
  // 이 기사를 실제로 가져온 Provider (예: "naver_news", "newsdata_io", "gnews")
  provider: string | null;
  // 같은 사건을 보도한 대표 기사의 id. null이면 자신이 대표이거나 단독 기사.
  cluster_head_id: number | null;
  // 같은 사건으로 묶인 다른 기사 수(조회된 목록 범위 내 근사치)
  related_count: number;
}

export interface NewsListResponse {
  ticker: string;
  provider_status: Record<string, string>;
  news: NewsItem[];
}

export interface DataSourceMeta {
  source_name: string | null;
  source_url: string | null;
  retrieved_at: string | null;
  data_period: string | null;
  calculation_method: string | null;
  is_estimated: boolean;
}

export interface ValueWithSource {
  value: number | null;
  meta: DataSourceMeta | null;
  is_na: boolean;
  na_reason: string | null;
  // 값이 없는 이유가 데이터 부족이 아니라 "적자/자본잠식" 등 구조적인 상태라서
  // 지표(배수) 자체가 의미를 갖지 못하는 경우 true. 이 경우 "N/A" 대신
  // na_reason에 담긴 짧은 라벨("적자", "자본잠식")을 그대로 보여준다.
  is_deficit: boolean;
}

export interface CompanyMetricsResponse {
  ticker: string;
  as_of: string | null;
  valuation: Record<string, ValueWithSource>;
  profitability: Record<string, ValueWithSource>;
  growth: Record<string, ValueWithSource>;
  financial_health: Record<string, ValueWithSource>;
  capital_cost: Record<string, ValueWithSource>;
}

export interface ScoreBreakdown {
  category: string;
  score: number | null;
  weight: number;
  components: Record<string, number | null>;
  is_na: boolean;
}

export interface CompositeScoreResponse {
  ticker: string;
  scores: ScoreBreakdown[];
  total_score: number | null;
  weights_config_version: string;
}

export interface SimpleLevel {
  label: string;
  detail: string;
}

export interface PeerComparisonRow {
  label: string;
  ticker: string | null; // 기업 행이면 종목코드, "업종 Median" 집계행이면 null(클릭 불가)
  per: number | null;
  per_is_deficit: boolean;
  pbr: number | null;
  pbr_is_deficit: boolean;
  ev_ebitda: number | null;
  ev_ebitda_is_deficit: boolean;
  // 감가상각비를 단독 계정으로 찾지 못해 현금흐름표 "조정" 합계로 EBITDA를 근사한 경우 true.
  ev_ebitda_is_estimated: boolean;
  roe: number | null;
}

export interface PeerComparisonResponse {
  ticker: string;
  industry: string | null;
  rows: PeerComparisonRow[];
  discount_premium: Record<string, number | null>;
}

export interface SimpleViewResponse {
  ticker: string;
  company_name: string;
  price_level: SimpleLevel;
  growth_level: SimpleLevel;
  profitability_level: SimpleLevel;
  financial_health_level: SimpleLevel;
  news_sentiment_level: SimpleLevel;
  historical_similarity_level: SimpleLevel;
  ai_outlook: SimpleLevel;
  risk_factors: string[];
  disclaimer: string;
}

export interface AskQuestionResponse {
  ticker: string;
  question: string;
  answer: string | null;
  // AI 서비스 자체를 사용할 수 없는 경우(API Key 미설정 등) true.
  is_unavailable: boolean;
  message: string | null;
  model: string | null;
  disclaimer: string;
}

export interface MarketReactionOut {
  return_0d: number | null;
  return_1d: number | null;
  return_5d: number | null;
  return_20d: number | null;
  return_60d: number | null;
  excess_return_1d: number | null;
  excess_return_5d: number | null;
  excess_return_20d: number | null;
  volatility_before: number | null;
  volatility_after: number | null;
  max_upside: number | null;
  max_drawdown: number | null;
  benchmark_index: string | null;
}

export interface EventStudyPoint {
  offset_days: number;
  return_pct: number | null;
  volume: number | null;
  volatility: number | null;
}

export interface EventStudyResponse {
  news_id: number;
  // "ok" | "insufficient_data" | "no_event" | "no_price_data"
  status: string;
  message: string | null;
  current_event: EventStudyPoint[];
  summary: MarketReactionOut | null;
  overlay_historical: Record<number, EventStudyPoint[]>;
}

export interface FinancialStatementOut {
  period: string;
  reported_at: string | null;
  available_at: string | null;
  revenue: number | null;
  operating_income: number | null;
  net_income: number | null;
  assets: number | null;
  liabilities: number | null;
  equity: number | null;
  operating_cash_flow: number | null;
  free_cash_flow: number | null;
}

export interface DCFAssumptions {
  revenue_growth_rate: number;
  operating_margin: number;
  tax_rate: number;
  capex_pct_revenue: number;
  working_capital_pct_revenue: number;
  wacc: number;
  terminal_growth_rate: number;
  projection_years: number;
}

export interface DCFResult {
  ticker: string;
  assumptions: DCFAssumptions;
  projected_fcf: number[];
  terminal_value: number;
  enterprise_value: number;
  net_debt: number | null;
  equity_value: number;
  shares_outstanding: number | null;
  estimated_price_per_share: number | null;
  current_price: number | null;
  upside_pct: number | null;
  note: string;
}

export interface WatchlistItemOut {
  id: number;
  ticker: string;
  company_name: string;
  current_price: number | null;
  price_change_pct: number | null;
  latest_important_news_title: string | null;
  notify_all_news: boolean;
  notify_event_types: string[] | null;
}

export interface PredictionResponse {
  ticker: string;
  predicted_at: string;
  data_period_start: string;
  data_period_end: string;
  model_used: string;
  last_trained_at: string | null;
  horizons: {
    horizon: string;
    up_probability: number | null;
    expected_return_pct: number | null;
    prediction_interval_low: number | null;
    prediction_interval_high: number | null;
    expected_volatility_change_pct: number | null;
    confidence: string | null;
  }[];
  positive_factors: { feature_name: string; feature_name_simple: string | null; contribution_pct: number; direction: string }[];
  negative_factors: { feature_name: string; feature_name_simple: string | null; contribution_pct: number; direction: string }[];
  is_mock: boolean;
  disclaimer: string;
}

export interface MarketSimulationResult {
  price_path: number[];
  volume_path: number[];
  volatility_path: number[];
  bubble_indicator: number | null;
  herding_indicator: number | null;
  is_mock: boolean;
  note: string;
}
