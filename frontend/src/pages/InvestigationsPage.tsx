import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  FileSearch,
  Filter,
  FolderOpen,
  RotateCcw,
  Search,
  User,
  X,
} from 'lucide-react';
import { api } from '../services/apiClient';
import { InvestigationItem } from '../types/api';
import { formatCurrencyINR } from '../utils/formatters';
import { Badge } from '../components/common/Badge';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import {
  InvestigationOutcomeBadge,
  InvestigationStatusBadge,
} from '../components/investigations/InvestigationBadges';
import { InvestigationWorkspaceModal } from '../components/investigations/InvestigationWorkspaceModal';

const PAGE_SIZE = 20;

export const InvestigationsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawAlertIdParam = searchParams.get('alert_id');
  const parsedAlertIdParam =
    rawAlertIdParam && /^\d+$/.test(rawAlertIdParam) && Number(rawAlertIdParam) > 0
      ? Number(rawAlertIdParam)
      : undefined;

  const rawInvIdParam = searchParams.get('investigation_id');
  const parsedInvIdParam =
    rawInvIdParam && /^\d+$/.test(rawInvIdParam) && Number(rawInvIdParam) > 0
      ? Number(rawInvIdParam)
      : null;

  const [investigations, setInvestigations] = useState<InvestigationItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<string>('all');
  const [assignedToInput, setAssignedToInput] = useState<string>('');
  const [assignedToQuery, setAssignedToQuery] = useState<string>('');
  const [offset, setOffset] = useState<number>(0);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedInvId, setSelectedInvId] = useState<number | null>(parsedInvIdParam);
  const [selectedInitialInv, setSelectedInitialInv] = useState<InvestigationItem | null>(
    null
  );

  // Sync deep-linked ?investigation_id= changes into workspace drawer selection
  useEffect(() => {
    if (parsedInvIdParam !== null) {
      setSelectedInvId(parsedInvIdParam);
    }
  }, [parsedInvIdParam]);

  const fetchInvestigations = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setLoading(true);
      }
      setError(null);
      try {
        const res = await api.getInvestigations({
          alert_id: parsedAlertIdParam,
          status: statusFilter !== 'all' ? statusFilter : undefined,
          outcome: outcomeFilter !== 'all' ? outcomeFilter : undefined,
          assigned_to: assignedToQuery || undefined,
          include_context: true,
          limit: PAGE_SIZE,
          offset,
        });
        setInvestigations(res);
      } catch (err: unknown) {
        if (!options?.silent) {
          const msg =
            err instanceof Error ? err.message : 'Failed to retrieve investigations.';
          setError(msg);
        }
      } finally {
        if (!options?.silent) {
          setLoading(false);
        }
      }
    },
    [parsedAlertIdParam, statusFilter, outcomeFilter, assignedToQuery, offset]
  );

  useEffect(() => {
    fetchInvestigations();
  }, [fetchInvestigations]);

  const handleApplyAnalystSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    setAssignedToQuery(assignedToInput.trim());
  };

  const hasActiveFilters =
    statusFilter !== 'all' ||
    outcomeFilter !== 'all' ||
    Boolean(assignedToQuery) ||
    parsedAlertIdParam !== undefined;

  const handleResetFilters = () => {
    setStatusFilter('all');
    setOutcomeFilter('all');
    setAssignedToInput('');
    setAssignedToQuery('');
    setOffset(0);
    if (searchParams.has('alert_id')) {
      const next = new URLSearchParams(searchParams);
      next.delete('alert_id');
      setSearchParams(next, { replace: true });
    }
  };

  const clearAlertFilter = () => {
    setOffset(0);
    const next = new URLSearchParams(searchParams);
    next.delete('alert_id');
    setSearchParams(next, { replace: true });
  };

  const openWorkspace = (inv: InvestigationItem) => {
    setSelectedInitialInv(inv);
    setSelectedInvId(inv.investigation_id);
  };

  const closeWorkspace = () => {
    setSelectedInvId(null);
    setSelectedInitialInv(null);
    if (searchParams.has('investigation_id')) {
      const next = new URLSearchParams(searchParams);
      next.delete('investigation_id');
      setSearchParams(next, { replace: true });
    }
  };

  const handleInvestigationUpdated = (updated: InvestigationItem) => {
    setSelectedInitialInv(updated);
    setInvestigations((prev) =>
      prev.map((item) =>
        item.investigation_id === updated.investigation_id ? updated : item
      )
    );
    fetchInvestigations({ silent: true });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Investigations Workspace
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Triage flagged fraud alerts, assign analysts, log timestamped case notes, and
          resolve investigations with verified outcomes.
        </p>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <label htmlFor="inv-status-filter" className="text-xs text-slate-400">
                Status:
              </label>
              <select
                id="inv-status-filter"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setOffset(0);
                }}
                className="px-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="all">All Statuses</option>
                <option value="OPEN">Open</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="RESOLVED">Resolved</option>
                <option value="CLOSED">Closed (Legacy)</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="inv-outcome-filter" className="text-xs text-slate-400">
                Outcome:
              </label>
              <select
                id="inv-outcome-filter"
                value={outcomeFilter}
                onChange={(e) => {
                  setOutcomeFilter(e.target.value);
                  setOffset(0);
                }}
                className="px-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="all">All Outcomes</option>
                <option value="CONFIRMED_FRAUD">Confirmed Fraud</option>
                <option value="LEGITIMATE">Legitimate</option>
              </select>
            </div>

            {parsedAlertIdParam !== undefined && (
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-950/50 border border-amber-800/60 text-xs text-amber-200">
                <span>Alert #{parsedAlertIdParam}</span>
                <button
                  type="button"
                  onClick={clearAlertFilter}
                  className="text-amber-300 hover:text-white"
                  aria-label="Clear alert filter"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          <form
            onSubmit={handleApplyAnalystSearch}
            className="flex items-center gap-2"
          >
            <div className="relative flex-1 sm:w-56">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                value={assignedToInput}
                onChange={(e) => setAssignedToInput(e.target.value)}
                placeholder="Filter by exact analyst..."
                className="w-full pl-8 pr-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition-colors"
            >
              Apply
            </button>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-medium inline-flex items-center gap-1"
              >
                <RotateCcw className="w-3 h-3" />
                Reset
              </button>
            )}
          </form>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <ErrorMessage
          title="Investigations Query Failed"
          message={error}
          onRetry={() => fetchInvestigations()}
        />
      )}

      {/* Investigations Table */}
      <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl overflow-hidden">
        {loading ? (
          <LoadingSpinner label="Fetching investigations..." />
        ) : investigations.length === 0 ? (
          <EmptyState
            icon={<FileSearch className="w-6 h-6 text-slate-500" />}
            title="No investigations found"
            description={
              hasActiveFilters
                ? 'No investigations match the selected status, outcome, or analyst criteria.'
                : 'No investigations exist yet. Open the Alerts page to initiate an investigation on a flagged alert.'
            }
            actionText={hasActiveFilters ? 'Clear All Filters' : undefined}
            onAction={hasActiveFilters ? handleResetFilters : undefined}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/70 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Case
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Linked Alert
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Transaction
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Analyst
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Outcome
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Notes / Summary
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold">
                    Last Updated
                  </th>
                  <th scope="col" className="px-4 py-3 font-semibold text-right">
                    Workspace
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {investigations.map((inv) => {
                  const linkedAlert = inv.alert;
                  const linkedTx = linkedAlert?.transaction;
                  const noteCount = inv.notes?.length || 0;
                  const latestNoteText =
                    noteCount > 0
                      ? inv.notes[noteCount - 1].content
                      : inv.findings;

                  return (
                    <tr
                      key={inv.investigation_id}
                      onClick={() => openWorkspace(inv)}
                      className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-slate-200 whitespace-nowrap">
                        INV-{inv.investigation_id}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <div className="flex flex-col gap-1">
                          <span className="font-mono text-amber-300">
                            Alert #{inv.alert_id}
                          </span>
                          {linkedAlert && (
                            <span className="text-[11px] text-slate-400">
                              {linkedAlert.alert_type} •{' '}
                              <span className="text-slate-300">{linkedAlert.status}</span>
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {linkedTx ? (
                          <div className="flex flex-col gap-0.5">
                            <span className="font-mono text-emerald-300">
                              {linkedTx.transaction_id}
                            </span>
                            <span className="text-[11px] text-slate-300 font-medium">
                              {formatCurrencyINR(linkedTx.amount)}
                              {linkedTx.fraud_prediction === 1 && (
                                <span className="ml-1.5 text-rose-400">• Fraud Flag</span>
                              )}
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-500 italic">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-300 whitespace-nowrap">
                        <span className="flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-slate-500" />
                          {inv.assigned_to || (
                            <span className="text-slate-500 italic">Unassigned</span>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <InvestigationStatusBadge status={inv.status} />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <InvestigationOutcomeBadge outcome={inv.outcome} />
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 max-w-xs">
                        <div className="flex items-center gap-2">
                          {noteCount > 0 && (
                            <Badge variant="neutral" size="sm">
                              {noteCount}
                            </Badge>
                          )}
                          <span className="truncate">
                            {latestNoteText || (
                              <span className="text-slate-600 italic">
                                No notes logged yet
                              </span>
                            )}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-slate-500" />
                          {new Date(inv.updated_at).toLocaleString()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openWorkspace(inv);
                          }}
                          type="button"
                          className="px-2.5 py-1 text-xs font-medium text-emerald-300 bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-800/50 rounded-lg transition-colors inline-flex items-center gap-1"
                          title="Open investigation workspace"
                        >
                          <FolderOpen className="w-3 h-3" />
                          Open Case
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 text-xs text-slate-400">
          <div>
            Showing{' '}
            <span className="font-medium text-slate-200">
              {investigations.length > 0 ? offset + 1 : 0}
            </span>{' '}
            to{' '}
            <span className="font-medium text-slate-200">
              {offset + investigations.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
              disabled={offset === 0 || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => {
                if (investigations.length === PAGE_SIZE) {
                  setOffset((prev) => prev + PAGE_SIZE);
                }
              }}
              disabled={investigations.length < PAGE_SIZE || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Analyst Slide-Over Workspace */}
      <InvestigationWorkspaceModal
        investigationId={selectedInvId}
        initialInvestigation={selectedInitialInv}
        onClose={closeWorkspace}
        onInvestigationUpdated={handleInvestigationUpdated}
      />
    </div>
  );
};
