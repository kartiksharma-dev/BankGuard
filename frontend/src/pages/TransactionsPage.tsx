import React, { useEffect, useState, useCallback } from 'react';
import {
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Calendar,
  CreditCard,
  MapPin,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { api } from '../services/apiClient';
import { AlertItem, TransactionItem } from '../types/api';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { EmptyState } from '../components/common/EmptyState';

const PAGE_SIZE = 15;

export const TransactionsPage: React.FC = () => {
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [alertsMap, setAlertsMap] = useState<Record<string, AlertItem>>({});
  const [totalReturned, setTotalReturned] = useState<number>(0);
  const [offset, setOffset] = useState<number>(0);
  const [customerIdFilter, setCustomerIdFilter] = useState<string>('');
  const [fraudFilter, setFraudFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Alert Creation Modal State
  const [selectedTx, setSelectedTx] = useState<TransactionItem | null>(null);
  const [alertTypeInput, setAlertTypeInput] = useState<string>('FRAUD_SUSPECTED');
  const [creatingAlert, setCreatingAlert] = useState<boolean>(false);
  const [alertActionFeedback, setAlertActionFeedback] = useState<string | null>(null);

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const fraudParam =
        fraudFilter === 'fraud' ? 1 : fraudFilter === 'normal' ? 0 : undefined;
      const [txRes, alertsRes] = await Promise.all([
        api.getTransactions({
          customer_id: customerIdFilter.trim() || undefined,
          fraud_prediction: fraudParam,
          limit: PAGE_SIZE,
          offset,
        }),
        api.getAlerts({ limit: 100 }).catch(() => [] as AlertItem[]),
      ]);

      const map: Record<string, AlertItem> = {};
      alertsRes.forEach((alert) => {
        if (!map[alert.transaction_id]) {
          map[alert.transaction_id] = alert;
        }
      });

      setTransactions(txRes.items);
      setTotalReturned(txRes.returned);
      setAlertsMap(map);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch transactions.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [customerIdFilter, fraudFilter, offset]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    fetchTransactions();
  };

  const handleNextPage = () => {
    if (totalReturned === PAGE_SIZE) {
      setOffset((prev) => prev + PAGE_SIZE);
    }
  };

  const handlePrevPage = () => {
    if (offset >= PAGE_SIZE) {
      setOffset((prev) => prev - PAGE_SIZE);
    }
  };

  const handleCreateAlert = async () => {
    if (!selectedTx) return;
    setCreatingAlert(true);
    setAlertActionFeedback(null);
    try {
      await api.createAlert({
        transaction_id: selectedTx.transaction_id,
        alert_type: alertTypeInput,
      });
      setAlertActionFeedback(`Alert successfully created for ${selectedTx.transaction_id}!`);
      setTimeout(() => {
        setSelectedTx(null);
        setAlertActionFeedback(null);
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create alert.';
      setAlertActionFeedback(`Error: ${msg}`);
    } finally {
      setCreatingAlert(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Transactions</h1>
        <p className="text-sm text-slate-400 mt-1">
          Search, filter, and inspect persisted financial transactions scored by the risk pipeline.
        </p>
      </div>

      {/* Informational Architecture Context Note */}
      <div className="p-3.5 bg-slate-900/60 border border-slate-800 rounded-xl flex items-start gap-3 text-xs text-slate-300">
        <Info className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-slate-200">Scoring & Triage Hierarchy:</span>{' '}
          <span className="text-slate-400">
            <strong>ML Prediction</strong> indicates the statistical probability classification from the XGBoost model (0 = Legitimate, 1 = Fraud).{' '}
            <strong>Alert / Triage Status</strong> independently flags transactions triggered by behavioral rules, velocity thresholds, or manual analyst reviews.
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Filter by Customer ID..."
              value={customerIdFilter}
              onChange={(e) => setCustomerIdFilter(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={fraudFilter}
              onChange={(e) => {
                setFraudFilter(e.target.value);
                setOffset(0);
              }}
              className="px-3 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="all">All Predictions</option>
              <option value="fraud">Fraud Detected (Flagged)</option>
              <option value="normal">Legitimate Only</option>
            </select>

            <button
              type="submit"
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Search
            </button>
          </div>
        </form>
      </div>

      {/* Error Message */}
      {error && (
        <ErrorMessage
          title="Transaction Query Failed"
          message={error}
          onRetry={fetchTransactions}
        />
      )}

      {/* Transactions Table */}
      <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl overflow-hidden">
        {loading ? (
          <LoadingSpinner label="Fetching transactions..." />
        ) : transactions.length === 0 ? (
          <EmptyState
            icon={<CreditCard className="w-6 h-6 text-slate-500" />}
            title="No transactions found"
            description={
              customerIdFilter || fraudFilter !== 'all'
                ? 'Try adjusting your customer filter or prediction criteria.'
                : 'No transactions have been ingested into the system yet.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/70 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">Transaction ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Customer ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Amount</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Category</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Location</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Date & Time</th>
                  <th scope="col" className="px-4 py-3 font-semibold">ML Prediction</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Alert Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {transactions.map((tx) => (
                  <tr key={tx.transaction_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-slate-200">
                      {tx.transaction_id}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-300">
                      {tx.customer_id}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-100">
                      ${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-xs capitalize text-slate-400">
                      {tx.merchant_category}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-slate-500" />
                        {tx.location}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-slate-500" />
                        {new Date(tx.timestamp).toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {tx.fraud_prediction === 1 ? (
                        <Badge variant="danger" size="sm">
                          <XCircle className="w-3 h-3" />
                          Fraud Flagged (1)
                        </Badge>
                      ) : (
                        <Badge variant="success" size="sm">
                          <CheckCircle2 className="w-3 h-3" />
                          Legitimate (0)
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {alertsMap[tx.transaction_id] ? (
                        <div className="flex flex-col gap-0.5">
                          <Badge variant="warning" size="sm">
                            <AlertTriangle className="w-3 h-3" />
                            {alertsMap[tx.transaction_id].alert_type}
                          </Badge>
                          <span className="text-[10px] text-amber-400/80 font-mono">
                            Status: {alertsMap[tx.transaction_id].status}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500">None</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setSelectedTx(tx)}
                        type="button"
                        className="px-2.5 py-1 text-xs font-medium text-amber-300 bg-amber-950/40 hover:bg-amber-900/60 border border-amber-800/50 rounded-lg transition-colors inline-flex items-center gap-1"
                        title="Raise an alert for this transaction"
                      >
                        <ShieldAlert className="w-3 h-3" />
                        Alert
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 text-xs text-slate-400">
          <div>
            Showing <span className="font-medium text-slate-200">{offset + 1}</span> to{' '}
            <span className="font-medium text-slate-200">{offset + transactions.length}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevPage}
              disabled={offset === 0 || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </button>
            <button
              onClick={handleNextPage}
              disabled={totalReturned < PAGE_SIZE || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Create Alert Modal */}
      {selectedTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-amber-400" />
                Create Fraud Alert
              </h3>
              <button
                onClick={() => setSelectedTx(null)}
                className="text-slate-400 hover:text-slate-200 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-xs space-y-1.5">
              <p><strong className="text-slate-400">Transaction ID:</strong> <span className="font-mono text-slate-200">{selectedTx.transaction_id}</span></p>
              <p><strong className="text-slate-400">Customer:</strong> <span className="text-slate-200">{selectedTx.customer_id}</span></p>
              <p><strong className="text-slate-400">Amount:</strong> <span className="text-slate-200">${selectedTx.amount.toFixed(2)}</span></p>
              <p><strong className="text-slate-400">Location:</strong> <span className="text-slate-200">{selectedTx.location}</span></p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Alert Type
              </label>
              <select
                value={alertTypeInput}
                onChange={(e) => setAlertTypeInput(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-amber-500"
              >
                <option value="FRAUD_SUSPECTED">FRAUD_SUSPECTED</option>
                <option value="HIGH_VELOCITY">HIGH_VELOCITY</option>
                <option value="UNUSUAL_LOCATION">UNUSUAL_LOCATION</option>
                <option value="HIGH_VALUE_OUTLIER">HIGH_VALUE_OUTLIER</option>
              </select>
            </div>

            {alertActionFeedback && (
              <p className={`text-xs ${alertActionFeedback.startsWith('Error') ? 'text-rose-400' : 'text-emerald-400'}`}>
                {alertActionFeedback}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedTx(null)}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreateAlert}
                disabled={creatingAlert}
                className="px-4 py-1.5 text-xs font-medium bg-amber-600 hover:bg-amber-500 text-white rounded-lg disabled:opacity-50"
              >
                {creatingAlert ? 'Creating...' : 'Create Alert'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
