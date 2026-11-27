import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertOctagon,
  Search,
  Filter,
  FileSearch,
  FolderOpen,
  Calendar,
  CheckCircle2,
  Clock,
  Radio,
} from 'lucide-react';
import { api, ApiError } from '../services/apiClient';
import { AlertItem, InvestigationItem } from '../types/api';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { EmptyState } from '../components/common/EmptyState';
import { InvestigationStatusBadge } from '../components/investigations/InvestigationBadges';
import { useRealtime } from '../context/RealtimeContext';

const LOOKUP_CONCURRENCY = 5;

interface QueuedLookupTask {
  alertId: number;
  ownerInstanceId: number;
  epoch: number;
  isStillValid: () => boolean;
  onDispatched: () => void;
  onSkipped: () => void;
  onSuccess: (found: InvestigationItem | null) => void;
  onError: () => void;
}

// Module-global HTTP coordinator enforcing <= 5 actual unresolved exact alert_id calls
let globalActiveHttpRequests = 0;
const globalPendingQueue: QueuedLookupTask[] = [];
let nextAlertsPageInstanceId = 1;

function purgePendingTasks(ownerInstanceId: number, epoch?: number): void {
  for (let i = globalPendingQueue.length - 1; i >= 0; i -= 1) {
    const task = globalPendingQueue[i];
    if (
      task.ownerInstanceId === ownerInstanceId &&
      (epoch === undefined || task.epoch === epoch)
    ) {
      globalPendingQueue.splice(i, 1);
      task.onSkipped();
    }
  }
}

function drainGlobalLookupQueue(): void {
  while (
    globalActiveHttpRequests < LOOKUP_CONCURRENCY &&
    globalPendingQueue.length > 0
  ) {
    const task = globalPendingQueue.shift()!;
    if (!task.isStillValid()) {
      task.onSkipped();
      continue;
    }

    // Reserve actual network slot BEFORE initiating async HTTP call
    globalActiveHttpRequests += 1;
    task.onDispatched();

    void api
      .getInvestigations({
        alert_id: task.alertId,
        limit: 1,
        include_context: false,
      })
      .then(
        (matches) => {
          task.onSuccess(matches[0] ?? null);
        },
        () => {
          task.onError();
        }
      )
      .finally(() => {
        globalActiveHttpRequests = Math.max(0, globalActiveHttpRequests - 1);
        drainGlobalLookupQueue();
      });
  }
}

export const AlertsPage: React.FC = () => {
  const navigate = useNavigate();

  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [transactionIdSearch, setTransactionIdSearch] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Two-tier cached investigation lookup + global concurrency coordinator
  const instanceIdRef = useRef<number>(nextAlertsPageInstanceId++);
  const lifecycleEpochRef = useRef<number>(0);
  const fetchSeqRef = useRef<number>(0);

  const knownInvestigationsRef = useRef<Map<number, InvestigationItem | null>>(new Map());
  const queuedAlertIdsRef = useRef<Set<number>>(new Set());
  const inFlightAlertIdsRef = useRef<Set<number>>(new Set());

  const snapshotCheckedRef = useRef<boolean>(false);
  const isSnapshotExhaustiveRef = useRef<boolean>(false);
  const snapshotPromiseRef = useRef<Promise<boolean> | null>(null);

  const isMountedRef = useRef<boolean>(false);
  const modalCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [investigationsMap, setInvestigationsMap] = useState<
    Record<number, InvestigationItem | null>
  >({});

  // Investigation creation modal
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [assignedToInput, setAssignedToInput] = useState<string>('analyst_1');
  const [initialNoteInput, setInitialNoteInput] = useState<string>('');
  const [submittingInv, setSubmittingInv] = useState<boolean>(false);
  const [invFeedback, setInvFeedback] = useState<string | null>(null);
  const [duplicateCaseInv, setDuplicateCaseInv] = useState<InvestigationItem | null>(null);

  const clearModalCloseTimer = useCallback(() => {
    if (modalCloseTimerRef.current !== null) {
      clearTimeout(modalCloseTimerRef.current);
      modalCloseTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    lifecycleEpochRef.current += 1;
    const ownerInstanceId = instanceIdRef.current;

    return () => {
      isMountedRef.current = false;
      const staleEpoch = lifecycleEpochRef.current;
      lifecycleEpochRef.current += 1;

      purgePendingTasks(ownerInstanceId, staleEpoch);
      queuedAlertIdsRef.current.clear();
      inFlightAlertIdsRef.current.clear();

      snapshotCheckedRef.current = false;
      isSnapshotExhaustiveRef.current = false;
      snapshotPromiseRef.current = null;

      clearModalCloseTimer();
    };
  }, [clearModalCloseTimer]);

  const syncInvestigationsState = useCallback(() => {
    if (!isMountedRef.current) return;
    setInvestigationsMap(Object.fromEntries(knownInvestigationsRef.current.entries()));
  }, []);

  const resetLookupState = useCallback(() => {
    const staleEpoch = lifecycleEpochRef.current;
    lifecycleEpochRef.current += 1;

    purgePendingTasks(instanceIdRef.current, staleEpoch);
    knownInvestigationsRef.current.clear();
    queuedAlertIdsRef.current.clear();
    inFlightAlertIdsRef.current.clear();

    snapshotCheckedRef.current = false;
    isSnapshotExhaustiveRef.current = false;
    snapshotPromiseRef.current = null;

    syncInvestigationsState();
  }, [syncInvestigationsState]);

  const ensureSnapshotLoaded = useCallback(async (capturedEpoch: number): Promise<boolean> => {
    if (snapshotCheckedRef.current) {
      return true;
    }

    if (!snapshotPromiseRef.current) {
      let currentPromise: Promise<boolean> | null = null;
      currentPromise = (async () => {
        try {
          const recentBatch = await api.getInvestigations({
            limit: 100,
            offset: 0,
            include_context: false,
          });
          if (!isMountedRef.current || lifecycleEpochRef.current !== capturedEpoch) {
            return false;
          }
          recentBatch.forEach((inv) => {
            knownInvestigationsRef.current.set(inv.alert_id, inv);
          });
          isSnapshotExhaustiveRef.current = recentBatch.length < 100;
          snapshotCheckedRef.current = true;
          return true;
        } catch {
          if (lifecycleEpochRef.current === capturedEpoch) {
            snapshotCheckedRef.current = false;
            isSnapshotExhaustiveRef.current = false;
          }
          return false;
        } finally {
          if (currentPromise && snapshotPromiseRef.current === currentPromise) {
            snapshotPromiseRef.current = null;
          }
        }
      })();

      snapshotPromiseRef.current = currentPromise;
    }

    return snapshotPromiseRef.current;
  }, []);

  const enqueueExactLookups = useCallback(
    (missingIds: number[], capturedEpoch: number) => {
      const ownerInstanceId = instanceIdRef.current;

      missingIds.forEach((alertId) => {
        if (
          knownInvestigationsRef.current.has(alertId) ||
          queuedAlertIdsRef.current.has(alertId) ||
          inFlightAlertIdsRef.current.has(alertId)
        ) {
          return;
        }

        queuedAlertIdsRef.current.add(alertId);
        globalPendingQueue.push({
          alertId,
          ownerInstanceId,
          epoch: capturedEpoch,
          isStillValid: () =>
            isMountedRef.current &&
            lifecycleEpochRef.current === capturedEpoch &&
            !knownInvestigationsRef.current.has(alertId) &&
            !inFlightAlertIdsRef.current.has(alertId),
          onDispatched: () => {
            if (lifecycleEpochRef.current !== capturedEpoch) return;
            queuedAlertIdsRef.current.delete(alertId);
            inFlightAlertIdsRef.current.add(alertId);
          },
          onSkipped: () => {
            if (lifecycleEpochRef.current === capturedEpoch) {
              queuedAlertIdsRef.current.delete(alertId);
            }
          },
          onSuccess: (found) => {
            if (!isMountedRef.current || lifecycleEpochRef.current !== capturedEpoch) {
              return;
            }
            inFlightAlertIdsRef.current.delete(alertId);
            if (!knownInvestigationsRef.current.get(alertId)) {
              knownInvestigationsRef.current.set(alertId, found);
              syncInvestigationsState();
            }
          },
          onError: () => {
            if (lifecycleEpochRef.current !== capturedEpoch) return;
            inFlightAlertIdsRef.current.delete(alertId);
          },
        });
      });

      drainGlobalLookupQueue();
    },
    [syncInvestigationsState]
  );

  const resolveInvestigationsForAlerts = useCallback(
    async (visibleAlerts: AlertItem[], capturedEpoch: number) => {
      if (visibleAlerts.length === 0) return;

      const snapshotReady = await ensureSnapshotLoaded(capturedEpoch);
      if (
        !snapshotReady ||
        !isMountedRef.current ||
        lifecycleEpochRef.current !== capturedEpoch
      ) {
        return;
      }

      if (isSnapshotExhaustiveRef.current) {
        visibleAlerts.forEach((alert) => {
          if (!knownInvestigationsRef.current.has(alert.alert_id)) {
            knownInvestigationsRef.current.set(alert.alert_id, null);
          }
        });
        syncInvestigationsState();
        return;
      }

      // Surface any matches already present in the Tier 1 snapshot immediately
      syncInvestigationsState();

      // Tier 2: More than 100 investigations may exist; queue uncached displayed IDs globally
      const missingIds = visibleAlerts
        .map((alert) => alert.alert_id)
        .filter(
          (id) =>
            !knownInvestigationsRef.current.has(id) &&
            !queuedAlertIdsRef.current.has(id) &&
            !inFlightAlertIdsRef.current.has(id)
        );

      if (missingIds.length > 0) {
        enqueueExactLookups(missingIds, capturedEpoch);
      }
    },
    [ensureSnapshotLoaded, enqueueExactLookups, syncInvestigationsState]
  );

  const fetchAlerts = useCallback(async () => {
    const capturedEpoch = lifecycleEpochRef.current;
    const seq = ++fetchSeqRef.current;

    setLoading(true);
    setError(null);
    try {
      const statusParam = statusFilter !== 'all' ? statusFilter : undefined;
      const res = await api.getAlerts({
        status: statusParam,
        transaction_id: transactionIdSearch.trim() || undefined,
        limit: 50,
      });
      if (
        !isMountedRef.current ||
        lifecycleEpochRef.current !== capturedEpoch ||
        fetchSeqRef.current !== seq
      ) {
        return;
      }
      setAlerts(res);
      void resolveInvestigationsForAlerts(res, capturedEpoch);
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        lifecycleEpochRef.current !== capturedEpoch ||
        fetchSeqRef.current !== seq
      ) {
        return;
      }
      const msg = err instanceof Error ? err.message : 'Failed to retrieve alerts.';
      setError(msg);
    } finally {
      if (
        isMountedRef.current &&
        lifecycleEpochRef.current === capturedEpoch &&
        fetchSeqRef.current === seq
      ) {
        setLoading(false);
      }
    }
  }, [statusFilter, transactionIdSearch, resolveInvestigationsForAlerts]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const { lastEvent, isSimulating } = useRealtime();

  // Dynamically prepend new alerts triggered by real-time transactions without re-scanning investigations
  useEffect(() => {
    if (!lastEvent || !lastEvent.data) return;

    let incomingAlert: AlertItem | null = null;
    if (lastEvent.type === 'ALERT_CREATED' && lastEvent.data.alert) {
      incomingAlert = lastEvent.data.alert;
    } else if (lastEvent.type === 'TRANSACTION_PROCESSED' && lastEvent.data.alert) {
      incomingAlert = lastEvent.data.alert;
    }

    if (incomingAlert) {
      if (!knownInvestigationsRef.current.has(incomingAlert.alert_id)) {
        knownInvestigationsRef.current.set(incomingAlert.alert_id, null);
        syncInvestigationsState();
      }

      const matchesSearch =
        !transactionIdSearch.trim() ||
        incomingAlert.transaction_id
          .toLowerCase()
          .includes(transactionIdSearch.trim().toLowerCase());
      const matchesStatus =
        statusFilter === 'all' ||
        incomingAlert.status.toUpperCase() === statusFilter.toUpperCase();

      if (matchesSearch && matchesStatus) {
        setAlerts((prev) => {
          if (prev.some((a) => a.alert_id === incomingAlert!.alert_id)) return prev;
          return [incomingAlert!, ...prev];
        });
      }
    }
  }, [lastEvent, statusFilter, transactionIdSearch, syncInvestigationsState]);

  const openInitiateModal = (alert: AlertItem) => {
    clearModalCloseTimer();
    setSelectedAlert(alert);
    setInitialNoteInput('');
    setInvFeedback(null);
    setDuplicateCaseInv(null);
  };

  const closeModal = () => {
    clearModalCloseTimer();
    setSelectedAlert(null);
    setInitialNoteInput('');
    setInvFeedback(null);
    setDuplicateCaseInv(null);
  };

  const handleStartInvestigation = async () => {
    if (!selectedAlert) return;
    clearModalCloseTimer();
    setSubmittingInv(true);
    setInvFeedback(null);
    setDuplicateCaseInv(null);
    try {
      const created = await api.createInvestigation({
        alert_id: selectedAlert.alert_id,
        assigned_to: assignedToInput.trim() || null,
        initial_note: initialNoteInput.trim() || null,
      });
      knownInvestigationsRef.current.set(created.alert_id, created);
      syncInvestigationsState();
      setInvFeedback(
        `Investigation INV-${created.investigation_id} initiated for Alert #${selectedAlert.alert_id}!`
      );
      modalCloseTimerRef.current = setTimeout(() => {
        modalCloseTimerRef.current = null;
        if (isMountedRef.current) {
          closeModal();
          fetchAlerts();
        }
      }, 1200);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        try {
          const matches = await api.getInvestigations({
            alert_id: selectedAlert.alert_id,
            limit: 1,
            include_context: false,
          });
          if (matches[0]) {
            knownInvestigationsRef.current.set(selectedAlert.alert_id, matches[0]);
            syncInvestigationsState();
            setDuplicateCaseInv(matches[0]);
          }
        } catch {
          // Preserve conflict feedback cleanly even if recovery query fails
        }
      }
      const msg = err instanceof Error ? err.message : 'Failed to start investigation.';
      setInvFeedback(`Error: ${msg}`);
    } finally {
      if (isMountedRef.current) {
        setSubmittingInv(false);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Fraud Alerts</h1>
          <p className="text-sm text-slate-400 mt-1">
            Monitor system-generated fraud alerts and triage potential violations for investigation.
          </p>
        </div>
        {isSimulating && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-950/60 text-amber-300 border border-amber-800/60 self-start sm:self-auto">
            <Radio className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>Live Alert Ingestion</span>
          </div>
        )}
      </div>

      {/* Filter / Search Bar */}
      <div className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Transaction ID..."
              value={transactionIdSearch}
              onChange={(e) => setTransactionIdSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="all">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="RESOLVED">Resolved</option>
              <option value="DISMISSED">Dismissed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <ErrorMessage
          title="Alerts Fetch Failed"
          message={error}
          onRetry={() => {
            resetLookupState();
            fetchAlerts();
          }}
        />
      )}

      {/* Alerts Table */}
      <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl overflow-hidden">
        {loading ? (
          <LoadingSpinner label="Fetching alerts..." />
        ) : alerts.length === 0 ? (
          <EmptyState
            icon={<AlertOctagon className="w-6 h-6 text-slate-500" />}
            title="No alerts found"
            description={
              statusFilter !== 'all' || transactionIdSearch
                ? 'Try adjusting your status or transaction search filters.'
                : 'No alerts have been recorded yet. Alerts are generated for high-risk transactions.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/70 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">Alert ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Transaction ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Alert Type</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Investigation</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Created At</th>
                  <th scope="col" className="px-4 py-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {alerts.map((alert) => {
                  const existingInv = investigationsMap[alert.alert_id] ?? null;

                  return (
                    <tr key={alert.alert_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-slate-200">
                        #{alert.alert_id}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-emerald-400">
                        {alert.transaction_id}
                      </td>
                      <td className="px-4 py-3 text-xs font-medium text-slate-200">
                        <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
                          {alert.alert_type}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {alert.status.toUpperCase() === 'OPEN' ? (
                          <Badge variant="warning" size="sm">
                            <Clock className="w-3 h-3" />
                            OPEN
                          </Badge>
                        ) : alert.status.toUpperCase() === 'RESOLVED' ? (
                          <Badge variant="success" size="sm">
                            <CheckCircle2 className="w-3 h-3" />
                            RESOLVED
                          </Badge>
                        ) : (
                          <Badge variant="neutral" size="sm">
                            {alert.status}
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {existingInv ? (
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-xs text-slate-300">
                              INV-{existingInv.investigation_id}
                            </span>
                            <InvestigationStatusBadge status={existingInv.status} />
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500 italic">None</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-slate-500" />
                          {new Date(alert.created_at).toLocaleString()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {existingInv ? (
                          <button
                            onClick={() =>
                              navigate(
                                `/investigations?investigation_id=${existingInv.investigation_id}`
                              )
                            }
                            type="button"
                            className="px-2.5 py-1 text-xs font-medium text-emerald-300 bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-800/50 rounded-lg transition-colors inline-flex items-center gap-1"
                            title="Open linked investigation workspace"
                          >
                            <FolderOpen className="w-3 h-3" />
                            Open Case
                          </button>
                        ) : (
                          <button
                            onClick={() => openInitiateModal(alert)}
                            type="button"
                            className="px-2.5 py-1 text-xs font-medium text-sky-300 bg-sky-950/40 hover:bg-sky-900/60 border border-sky-800/50 rounded-lg transition-colors inline-flex items-center gap-1"
                            title="Investigate this alert"
                          >
                            <FileSearch className="w-3 h-3" />
                            Investigate
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Open Investigation */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <FileSearch className="w-5 h-5 text-sky-400" />
                Initiate Investigation
              </h3>
              <button
                onClick={closeModal}
                type="button"
                className="text-slate-400 hover:text-slate-200 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-xs space-y-1.5">
              <p><strong className="text-slate-400">Alert ID:</strong> <span className="font-mono text-slate-200">#{selectedAlert.alert_id}</span></p>
              <p><strong className="text-slate-400">Transaction:</strong> <span className="font-mono text-emerald-400">{selectedAlert.transaction_id}</span></p>
              <p><strong className="text-slate-400">Alert Type:</strong> <span className="text-slate-200">{selectedAlert.alert_type}</span></p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Assign Analyst
              </label>
              <input
                type="text"
                maxLength={100}
                placeholder="e.g. analyst_1, compliance_desk"
                value={assignedToInput}
                onChange={(e) => setAssignedToInput(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Initial Triage Note <span className="text-slate-500 font-normal">(optional)</span>
              </label>
              <textarea
                rows={3}
                placeholder="Optional initial triage observation or escalation note..."
                value={initialNoteInput}
                onChange={(e) => setInitialNoteInput(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>

            {invFeedback && (
              <p className={`text-xs ${invFeedback.startsWith('Error') ? 'text-rose-400' : 'text-emerald-400'}`}>
                {invFeedback}
              </p>
            )}

            <div className="flex flex-wrap justify-end gap-2 pt-2">
              {duplicateCaseInv && (
                <button
                  type="button"
                  onClick={() =>
                    navigate(
                      `/investigations?investigation_id=${duplicateCaseInv.investigation_id}`
                    )
                  }
                  className="px-3.5 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg inline-flex items-center gap-1"
                >
                  <FolderOpen className="w-3.5 h-3.5" />
                  Open Existing Case (INV-{duplicateCaseInv.investigation_id})
                </button>
              )}
              <button
                type="button"
                onClick={closeModal}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStartInvestigation}
                disabled={submittingInv}
                className="px-4 py-1.5 text-xs font-medium bg-sky-600 hover:bg-sky-500 text-white rounded-lg disabled:opacity-50"
              >
                {submittingInv ? 'Creating...' : 'Open Investigation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
