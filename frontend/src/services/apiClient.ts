import {
  AlertCreatePayload,
  AlertItem,
  DashboardChartsData,
  DashboardStats,
  HealthResponse,
  InvestigationAssignPayload,
  InvestigationCreatePayload,
  InvestigationItem,
  InvestigationNotePayload,
  InvestigationResolvePayload,
  InvestigationStartPayload,
  InvestigationUpdatePayload,
  SimulationStartPayload,
  SimulationStatusResponse,
  TransactionsResponse,
} from '../types/api';

const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL;
// If empty or undefined, use relative path which triggers Vite's proxy '/api' -> 'http://127.0.0.1:8000'
export const API_BASE_URL = (RAW_BASE_URL !== undefined && RAW_BASE_URL !== '')
  ? RAW_BASE_URL.replace(/\/+$/, '')
  : '';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === 'string') {
    const trimmed = detail.trim();
    return trimmed || null;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item.trim();
        if (item && typeof item === 'object' && 'msg' in item) {
          const msg = String((item as { msg: unknown }).msg);
          return msg.replace(/^Value error,\s*/i, '').trim();
        }
        return null;
      })
      .filter((msg): msg is string => Boolean(msg));
    return messages.length > 0 ? messages.join('; ') : null;
  }
  return null;
}

const REQUEST_TIMEOUT_MS = 10_000;

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Abort the request after REQUEST_TIMEOUT_MS to prevent indefinite hangs
  // when the backend is slow or PostgreSQL is unreachable.
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      let errorMessage = `HTTP error ${response.status}: ${response.statusText}`;
      let errorData: unknown = null;
      try {
        errorData = await response.json();
        if (errorData && typeof errorData === 'object' && 'detail' in errorData) {
          const parsedDetail = formatApiDetail((errorData as { detail: unknown }).detail);
          if (parsedDetail) {
            errorMessage = parsedDetail;
          }
        }
      } catch {
        // Response was not JSON
      }
      throw new ApiError(errorMessage, response.status, errorData);
    }

    // 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    // AbortError means the 10-second timeout fired before the server responded.
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError(
        'Request timed out after 10 seconds. The backend may be unavailable or overloaded.',
        0,
      );
    }
    const message = err instanceof Error ? err.message : 'Unknown network failure';
    throw new ApiError(`Network error connecting to BankGuard backend: ${message}`, 0);
  } finally {
    // Always clear the timer so it does not fire after the request settles.
    clearTimeout(timeoutId);
  }
}

export const api = {
  // System Health
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health');
  },

  // Dashboard Stats & Charts
  async getDashboardStats(): Promise<DashboardStats> {
    return request<DashboardStats>('/api/v1/dashboard/stats');
  },

  async getDashboardCharts(): Promise<DashboardChartsData> {
    return request<DashboardChartsData>('/api/v1/dashboard/charts');
  },

  // Transactions
  async getTransactions(params?: {
    customer_id?: string;
    fraud_prediction?: number;
    limit?: number;
    offset?: number;
  }): Promise<TransactionsResponse> {
    const query = new URLSearchParams();
    if (params?.customer_id) query.set('customer_id', params.customer_id);
    if (params?.fraud_prediction !== undefined) query.set('fraud_prediction', String(params.fraud_prediction));
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    if (params?.offset !== undefined) query.set('offset', String(params.offset));

    const queryString = query.toString();
    const endpoint = `/api/v1/transactions${queryString ? `?${queryString}` : ''}`;
    return request<TransactionsResponse>(endpoint);
  },

  // Alerts
  async getAlerts(params?: {
    transaction_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<AlertItem[]> {
    const query = new URLSearchParams();
    if (params?.transaction_id) query.set('transaction_id', params.transaction_id);
    if (params?.status) query.set('status', params.status);
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    if (params?.offset !== undefined) query.set('offset', String(params.offset));

    const queryString = query.toString();
    const endpoint = `/api/v1/alerts${queryString ? `?${queryString}` : ''}`;
    return request<AlertItem[]>(endpoint);
  },

  async createAlert(payload: AlertCreatePayload): Promise<AlertItem> {
    return request<AlertItem>('/api/v1/alerts', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getAlertById(alertId: number): Promise<AlertItem> {
    return request<AlertItem>(`/api/v1/alerts/${alertId}`);
  },

  // Investigations
  async getInvestigations(params?: {
    alert_id?: number;
    status?: string;
    assigned_to?: string;
    outcome?: string;
    include_context?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<InvestigationItem[]> {
    const query = new URLSearchParams();
    if (params?.alert_id !== undefined) query.set('alert_id', String(params.alert_id));
    if (params?.status) query.set('status', params.status);
    if (params?.assigned_to) query.set('assigned_to', params.assigned_to);
    if (params?.outcome) query.set('outcome', params.outcome);
    if (params?.include_context !== undefined) {
      query.set('include_context', String(params.include_context));
    }
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    if (params?.offset !== undefined) query.set('offset', String(params.offset));

    const queryString = query.toString();
    const endpoint = `/api/v1/investigations${queryString ? `?${queryString}` : ''}`;
    return request<InvestigationItem[]>(endpoint);
  },

  async createInvestigation(payload: InvestigationCreatePayload): Promise<InvestigationItem> {
    return request<InvestigationItem>('/api/v1/investigations', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getInvestigationById(
    investigationId: number,
    includeContext: boolean = true
  ): Promise<InvestigationItem> {
    return request<InvestigationItem>(
      `/api/v1/investigations/${investigationId}?include_context=${includeContext}`
    );
  },

  async assignInvestigation(
    investigationId: number,
    payload: InvestigationAssignPayload
  ): Promise<InvestigationItem> {
    return request<InvestigationItem>(`/api/v1/investigations/${investigationId}/assign`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async startInvestigation(
    investigationId: number,
    payload?: InvestigationStartPayload
  ): Promise<InvestigationItem> {
    return request<InvestigationItem>(`/api/v1/investigations/${investigationId}/start`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  },

  async addInvestigationNote(
    investigationId: number,
    payload: InvestigationNotePayload
  ): Promise<InvestigationItem> {
    return request<InvestigationItem>(`/api/v1/investigations/${investigationId}/notes`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async resolveInvestigation(
    investigationId: number,
    payload: InvestigationResolvePayload
  ): Promise<InvestigationItem> {
    return request<InvestigationItem>(`/api/v1/investigations/${investigationId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async updateInvestigation(
    investigationId: number,
    payload: InvestigationUpdatePayload
  ): Promise<InvestigationItem> {
    return request<InvestigationItem>(`/api/v1/investigations/${investigationId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  // Simulation Stream Management (Phase 8)
  async getSimulationStatus(): Promise<SimulationStatusResponse> {
    return request<SimulationStatusResponse>('/api/v1/simulator/stream/status');
  },

  async startSimulationStream(payload?: SimulationStartPayload): Promise<SimulationStatusResponse> {
    return request<SimulationStatusResponse>('/api/v1/simulator/stream/start', {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  },

  async stopSimulationStream(): Promise<SimulationStatusResponse> {
    return request<SimulationStatusResponse>('/api/v1/simulator/stream/stop', {
      method: 'POST',
    });
  },
};
