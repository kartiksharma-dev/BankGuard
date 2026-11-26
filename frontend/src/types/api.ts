export interface TransactionItem {
  transaction_id: string;
  customer_id: string;
  amount: number;
  merchant_category: string;
  device_id: string;
  location: string;
  timestamp: string;
  payment_method: string;
  transaction_type: string;
  fraud_prediction: number; // 0: Legitimate, 1: Fraud
  created_at: string;
}

export interface TransactionsResponse {
  items: TransactionItem[];
  limit: number;
  offset: number;
  returned: number;
}

export interface AlertItem {
  alert_id: number;
  transaction_id: string;
  alert_type: string;
  status: 'OPEN' | 'RESOLVED' | 'DISMISSED' | string;
  created_at: string;
}

export interface AlertCreatePayload {
  transaction_id: string;
  alert_type: string;
}

export interface InvestigationItem {
  investigation_id: number;
  alert_id: number;
  assigned_to: string | null;
  status: 'OPEN' | 'IN_PROGRESS' | 'CLOSED' | string;
  findings: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationCreatePayload {
  alert_id: number;
  assigned_to?: string | null;
}

export interface InvestigationUpdatePayload {
  assigned_to?: string | null;
  status?: string | null;
  findings?: string | null;
}

export interface DashboardStats {
  total_transactions: number;
  fraud_detected: number;
  high_risk_transactions: number;
  open_alerts: number;
  investigations_in_progress: number;
  fraud_rate: number;
}

export interface ChartVolumePoint {
  date: string;
  total: number;
  fraud: number;
}

export interface ChartCategoryPoint {
  category: string;
  total: number;
  fraud: number;
}

export interface ChartLocationPoint {
  location: string;
  total: number;
  fraud: number;
}

export interface ChartRiskPoint {
  name: string;
  value: number;
  color: string;
}

export interface DashboardChartsData {
  volume_by_date: ChartVolumePoint[];
  category_distribution: ChartCategoryPoint[];
  location_distribution: ChartLocationPoint[];
  risk_distribution: ChartRiskPoint[];
}

export interface HealthResponse {
  status: string;
  application?: string;
  version?: string;
}

export interface RiskAssessmentData {
  model_prediction: number;
  behavioral_risk_score?: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  recommended_action: 'ALLOW' | 'REVIEW';
}

export interface WebSocketTransactionPayload {
  transaction: TransactionItem;
  risk_assessment: RiskAssessmentData;
  alert: AlertItem | null;
}

export interface WebSocketAlertPayload {
  alert: AlertItem;
}

export interface WebSocketTransactionEvent {
  type: 'TRANSACTION_PROCESSED' | 'ALERT_CREATED' | 'CONNECTION_ESTABLISHED' | 'PONG';
  timestamp?: string;
  message?: string;
  data?: WebSocketTransactionPayload | WebSocketAlertPayload | any;
}

export interface SimulationStatusResponse {
  is_running: boolean;
  generation_interval: number;
  rate_per_second: number;
  scenario: string;
  total_generated: number;
  total_successful: number;
  total_failed: number;
  total_fraud: number;
  total_alerts: number;
  connected_clients: number;
  last_error: string | null;
  started_at: string | null;
  stopped_at: string | null;
}

export interface SimulationStartPayload {
  rate_per_second?: number;
  scenario?: string;
}
