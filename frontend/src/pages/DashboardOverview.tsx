import React, { useEffect, useState, useCallback } from 'react';
import {
  CreditCard,
  AlertTriangle,
  ShieldAlert,
  BellRing,
  FileSearch,
  Percent,
} from 'lucide-react';
import { api } from '../services/apiClient';
import { DashboardChartsData, DashboardStats } from '../types/api';
import { StatCard } from '../components/common/StatCard';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { TransactionVolumeChart } from '../components/charts/TransactionVolumeChart';
import { RiskDistributionChart } from '../components/charts/RiskDistributionChart';
import { CategoryChart } from '../components/charts/CategoryChart';
import { LocationChart } from '../components/charts/LocationChart';

export const DashboardOverview: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [charts, setCharts] = useState<DashboardChartsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, chartsRes] = await Promise.all([
        api.getDashboardStats(),
        api.getDashboardCharts(),
      ]);
      setStats(statsRes);
      setCharts(chartsRes);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch dashboard data.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Dashboard Overview</h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time transaction scoring, XGBoost fraud detection, and risk operations.
          </p>
        </div>
      </div>

      {/* Error notification if API fails */}
      {error && (
        <ErrorMessage
          title="Data Connection Error"
          message={error}
          onRetry={fetchData}
        />
      )}

      {/* KPI Statistic Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          title="Total Transactions"
          value={stats ? stats.total_transactions.toLocaleString() : '—'}
          subtitle="All transactions recorded in PostgreSQL"
          definition="Total count of persisted transactions ingested through the scoring pipeline."
          icon={<CreditCard className="w-5 h-5 text-emerald-400" />}
          loading={loading}
        />

        <StatCard
          title="Fraud Detected"
          value={stats ? stats.fraud_detected.toLocaleString() : '—'}
          subtitle="Flagged by XGBoost model"
          definition="Transactions where the production ML model classified fraud_prediction = 1."
          icon={<AlertTriangle className="w-5 h-5" />}
          variant="danger"
          loading={loading}
        />

        <StatCard
          title="High-Risk Transactions"
          value={stats ? stats.high_risk_transactions.toLocaleString() : '—'}
          subtitle="Transactions flagged or alerted"
          definition="Total transactions classified as high risk based on model predictions or active alert triggers."
          icon={<ShieldAlert className="w-5 h-5" />}
          variant="warning"
          loading={loading}
        />

        <StatCard
          title="Open Alerts"
          value={stats ? stats.open_alerts.toLocaleString() : '—'}
          subtitle="Awaiting triage & review"
          definition="Total alerts in the alerts table with status = 'OPEN'."
          icon={<BellRing className="w-5 h-5" />}
          variant="warning"
          loading={loading}
        />

        <StatCard
          title="Investigations In Progress"
          value={stats ? stats.investigations_in_progress.toLocaleString() : '—'}
          subtitle="Assigned to fraud analysts"
          definition="Investigations currently being evaluated with status = 'IN_PROGRESS'."
          icon={<FileSearch className="w-5 h-5" />}
          loading={loading}
        />

        <StatCard
          title="Fraud Rate"
          value={stats ? `${stats.fraud_rate.toFixed(2)}%` : '—'}
          subtitle="Fraudulent / Total volume"
          definition="Proportion of total processed transactions identified as fraud: (fraud_detected / total_transactions * 100)%."
          icon={<Percent className="w-5 h-5" />}
          variant={stats && stats.fraud_rate > 2.0 ? 'danger' : 'success'}
          loading={loading}
        />
      </div>

      {/* Analytics Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transaction Volume Timeline (2 cols on large screen) */}
        <div className="lg:col-span-2 p-5 bg-slate-900/70 border border-slate-800/80 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-100">Transaction Volume & Fraud Trends</h2>
              <p className="text-xs text-slate-400 mt-0.5">Timeline distribution of daily processed volume and flagged fraud</p>
            </div>
          </div>
          <TransactionVolumeChart
            data={charts?.volume_by_date || []}
            loading={loading}
          />
        </div>

        {/* Risk Distribution Donut (1 col on large screen) */}
        <div className="p-5 bg-slate-900/70 border border-slate-800/80 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-100">Risk Distribution</h2>
              <p className="text-xs text-slate-400 mt-0.5">Legitimate vs confirmed high-risk transactions</p>
            </div>
          </div>
          <RiskDistributionChart
            data={charts?.risk_distribution || []}
            loading={loading}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Breakdown */}
        <div className="p-5 bg-slate-900/70 border border-slate-800/80 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-100">Transactions by Merchant Category</h2>
              <p className="text-xs text-slate-400 mt-0.5">Volume and fraud occurrence across merchant industries</p>
            </div>
          </div>
          <CategoryChart
            data={charts?.category_distribution || []}
            loading={loading}
          />
        </div>

        {/* Location Breakdown */}
        <div className="p-5 bg-slate-900/70 border border-slate-800/80 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-100">Top Locations by Volume</h2>
              <p className="text-xs text-slate-400 mt-0.5">Geographic concentration of transactions</p>
            </div>
          </div>
          <LocationChart
            data={charts?.location_distribution || []}
            loading={loading}
          />
        </div>
      </div>
    </div>
  );
};
