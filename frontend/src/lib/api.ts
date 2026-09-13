/**
 * 백엔드 FastAPI 호출 공통 클라이언트.
 *
 * UI 코드에서 직접 데이터 수집/ML을 실행하지 않고, 반드시 이 클라이언트를 통해
 * Backend API만 호출한다 (요구사항 2: Frontend/Backend 레이어 분리).
 */
import type {
  AskQuestionResponse,
  CompanyDetail,
  CompanyMetricsResponse,
  CompanySearchResponse,
  CompositeScoreResponse,
  DCFAssumptions,
  DCFResult,
  EventStudyResponse,
  FinancialStatementOut,
  MarketSimulationResult,
  NewsListResponse,
  PeerComparisonResponse,
  PredictionResponse,
  PriceHistoryResponse,
  SimpleViewResponse,
  WatchlistItemOut,
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // 응답 본문이 JSON이 아닐 수 있음
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  searchCompanies: (q: string) =>
    request<CompanySearchResponse>(`/companies/search?q=${encodeURIComponent(q)}`),

  getCompanyDetail: (ticker: string) => request<CompanyDetail>(`/companies/${ticker}`),

  getCompanyPrices: (ticker: string, period: string) =>
    request<PriceHistoryResponse>(`/companies/${ticker}/prices?period=${period}`),

  getCompanyFinancials: (ticker: string) =>
    request<FinancialStatementOut[]>(`/companies/${ticker}/financials`),

  getCompanyMetrics: (ticker: string) =>
    request<CompanyMetricsResponse>(`/companies/${ticker}/metrics`),

  getCompanyScore: (ticker: string) =>
    request<CompositeScoreResponse>(`/companies/${ticker}/score`),

  getCompanyPeers: (ticker: string) =>
    request<PeerComparisonResponse>(`/companies/${ticker}/peers`),

  getCompanySimpleView: (ticker: string) =>
    request<SimpleViewResponse>(`/companies/${ticker}/simple-view`),

  getCompanyNews: (ticker: string) => request<NewsListResponse>(`/companies/${ticker}/news`),

  askCompanyQuestion: (ticker: string, question: string) =>
    request<AskQuestionResponse>(`/companies/${ticker}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  getEventStudy: (newsId: number) => request<EventStudyResponse>(`/news/${newsId}/event-study`),

  getPrediction: (ticker: string) => request<PredictionResponse>(`/companies/${ticker}/prediction`),

  runDcf: (ticker: string, assumptions?: Partial<DCFAssumptions>) =>
    request<DCFResult>(`/dcf`, {
      method: "POST",
      body: JSON.stringify({ ticker, assumptions }),
    }),

  getWatchlist: () => request<WatchlistItemOut[]>(`/watchlist`),

  addWatchlist: (ticker: string) =>
    request(`/watchlist`, { method: "POST", body: JSON.stringify({ ticker }) }),

  removeWatchlist: (ticker: string) => request(`/watchlist/${ticker}`, { method: "DELETE" }),

  runSimulation: (payload: unknown) =>
    request<MarketSimulationResult>(`/simulation`, { method: "POST", body: JSON.stringify(payload) }),

  runAnalysis: (payload: unknown) =>
    request(`/analysis/run`, { method: "POST", body: JSON.stringify(payload) }),

  getAnalysisResult: (jobId: number) => request(`/analysis/${jobId}`),
};
