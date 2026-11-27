import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertOctagon,
  Calendar,
  CheckCircle2,
  CreditCard,
  FileText,
  Lock,
  MapPin,
  MessageSquarePlus,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  UserMinus,
  X,
} from 'lucide-react';
import { api } from '../../services/apiClient';
import {
  InvestigationItem,
  InvestigationOutcome,
} from '../../types/api';
import { formatCurrencyINR } from '../../utils/formatters';
import { Badge } from '../common/Badge';
import { ErrorMessage } from '../common/ErrorMessage';
import { LoadingSpinner } from '../common/LoadingSpinner';
import {
  InvestigationOutcomeBadge,
  InvestigationStatusBadge,
  isInvestigationTerminal,
} from './InvestigationBadges';

interface InvestigationWorkspaceModalProps {
  investigationId: number | null;
  initialInvestigation: InvestigationItem | null;
  onClose: () => void;
  onInvestigationUpdated: (updated: InvestigationItem) => void;
}

type ActionKey = 'assign' | 'unassign' | 'start' | 'note' | 'resolve' | null;

function mergeInvestigationContext(
  previous: InvestigationItem | null,
  updated: InvestigationItem
): InvestigationItem {
  return {
    ...updated,
    alert: updated.alert ?? previous?.alert ?? null,
  };
}

export const InvestigationWorkspaceModal: React.FC<InvestigationWorkspaceModalProps> = ({
  investigationId,
  initialInvestigation,
  onClose,
  onInvestigationUpdated,
}) => {
  const [investigation, setInvestigation] = useState<InvestigationItem | null>(
    initialInvestigation
  );
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [activeAction, setActiveAction] = useState<ActionKey>(null);
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // Assign state
  const [assigneeInput, setAssigneeInput] = useState<string>('');
  const [assignNoteInput, setAssignNoteInput] = useState<string>('');

  // Start state
  const [startNoteInput, setStartNoteInput] = useState<string>('');

  // Add note state
  const [noteInput, setNoteInput] = useState<string>('');
  const [noteAuthorInput, setNoteAuthorInput] = useState<string>('');

  // Resolve state
  const [resolveOutcome, setResolveOutcome] =
    useState<InvestigationOutcome>('CONFIRMED_FRAUD');
  const [resolveFindingsInput, setResolveFindingsInput] = useState<string>('');
  const [resolveAuthorInput, setResolveAuthorInput] = useState<string>('');

  const initialInvRef = useRef<InvestigationItem | null>(initialInvestigation);
  initialInvRef.current = initialInvestigation;
  const latestInvIdRef = useRef<number | null>(investigationId);
  latestInvIdRef.current = investigationId;

  const loadDetails = useCallback(
    async (id: number, showSpinner: boolean) => {
      if (showSpinner) {
        setDetailLoading(true);
      }
      setDetailError(null);
      try {
        const fresh = await api.getInvestigationById(id, true);
        if (latestInvIdRef.current !== id) return;
        setInvestigation((prev) => mergeInvestigationContext(prev, fresh));
        setAssigneeInput(fresh.assigned_to || '');
      } catch (err: unknown) {
        if (latestInvIdRef.current !== id) return;
        const msg =
          err instanceof Error ? err.message : 'Failed to load investigation details.';
        setDetailError(msg);
      } finally {
        if (latestInvIdRef.current === id || latestInvIdRef.current === null) {
          setDetailLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    if (investigationId === null) {
      setInvestigation(null);
      setDetailError(null);
      setFeedback(null);
      return;
    }

    const seed = initialInvRef.current;
    const matchingInitial =
      seed && seed.investigation_id === investigationId ? seed : null;

    setInvestigation(matchingInitial);
    setAssigneeInput(matchingInitial?.assigned_to || '');
    setAssignNoteInput('');
    setStartNoteInput('');
    setNoteInput('');
    setNoteAuthorInput('');
    setResolveOutcome('CONFIRMED_FRAUD');
    setResolveFindingsInput('');
    setResolveAuthorInput('');
    setFeedback(null);
    setDetailError(null);

    let cancelled = false;
    const run = async () => {
      if (!matchingInitial) {
        setDetailLoading(true);
      }
      try {
        const fresh = await api.getInvestigationById(investigationId, true);
        if (cancelled) return;
        setInvestigation((prev) => mergeInvestigationContext(prev, fresh));
        setAssigneeInput(fresh.assigned_to || '');
      } catch (err: unknown) {
        if (cancelled) return;
        if (!matchingInitial) {
          const msg =
            err instanceof Error
              ? err.message
              : 'Failed to retrieve investigation details.';
          setDetailError(msg);
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [investigationId]);

  useEffect(() => {
    if (investigationId === null) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && activeAction === null) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [investigationId, activeAction, onClose]);

  if (investigationId === null) {
    return null;
  }

  const runAction = async (
    actionKey: Exclude<ActionKey, null>,
    operation: () => Promise<InvestigationItem>,
    successMessage: string,
    afterSuccess?: (merged: InvestigationItem) => void
  ) => {
    setActiveAction(actionKey);
    setFeedback(null);
    try {
      const updated = await operation();
      const merged = mergeInvestigationContext(investigation, updated);
      setInvestigation(merged);
      setDetailError(null);
      setAssigneeInput(merged.assigned_to || '');
      onInvestigationUpdated(merged);
      setFeedback({ type: 'success', message: successMessage });
      if (afterSuccess) {
        afterSuccess(merged);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Investigation action failed.';
      setFeedback({ type: 'error', message: msg });
    } finally {
      setActiveAction(null);
    }
  };

  const handleAssignSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!investigation) return;
    const trimmed = assigneeInput.trim();
    if (!trimmed) {
      setFeedback({
        type: 'error',
        message: 'Enter an analyst name/ID or click Unassign to clear the assignee.',
      });
      return;
    }
    if (trimmed.length > 100) {
      setFeedback({
        type: 'error',
        message: 'Assigned analyst must not exceed 100 characters.',
      });
      return;
    }

    await runAction(
      'assign',
      () =>
        api.assignInvestigation(investigation.investigation_id, {
          assigned_to: trimmed,
          note: assignNoteInput.trim() || null,
        }),
      `Case INV-${investigation.investigation_id} assigned to ${trimmed}.`,
      () => setAssignNoteInput('')
    );
  };

  const handleUnassign = async () => {
    if (!investigation) return;
    await runAction(
      'unassign',
      () =>
        api.assignInvestigation(investigation.investigation_id, {
          assigned_to: null,
          note: assignNoteInput.trim() || null,
        }),
      `Case INV-${investigation.investigation_id} unassigned.`,
      () => setAssignNoteInput('')
    );
  };

  const handleStartInvestigation = async () => {
    if (!investigation) return;
    await runAction(
      'start',
      () =>
        api.startInvestigation(
          investigation.investigation_id,
          startNoteInput.trim() ? { note: startNoteInput.trim() } : {}
        ),
      `Case INV-${investigation.investigation_id} transitioned to IN_PROGRESS.`,
      () => setStartNoteInput('')
    );
  };

  const handleAddNoteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!investigation) return;
    const trimmed = noteInput.trim();
    if (!trimmed) {
      setFeedback({
        type: 'error',
        message: 'Investigation note cannot be empty.',
      });
      return;
    }

    await runAction(
      'note',
      () =>
        api.addInvestigationNote(investigation.investigation_id, {
          note: trimmed,
          author: noteAuthorInput.trim() || null,
        }),
      'Timestamped note appended to case timeline.',
      () => setNoteInput('')
    );
  };

  const normalizedStatus = (investigation?.status || '').toUpperCase();
  const isTerminal = investigation ? isInvestigationTerminal(investigation.status) : false;
  const isOpen = normalizedStatus === 'OPEN';
  const isInProgress = normalizedStatus === 'IN_PROGRESS';
  const hasExistingFindingsOrNotes = Boolean(
    investigation &&
      ((investigation.findings && investigation.findings.trim().length > 0) ||
        (investigation.notes && investigation.notes.length > 0))
  );

  const handleResolveSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!investigation) return;

    const cleanFindings = resolveFindingsInput.trim();
    if (!cleanFindings && !hasExistingFindingsOrNotes) {
      setFeedback({
        type: 'error',
        message:
          'Resolution findings are required because no prior notes or findings are logged.',
      });
      return;
    }

    const expectedAlertStatus =
      resolveOutcome === 'CONFIRMED_FRAUD' ? 'RESOLVED' : 'DISMISSED';

    await runAction(
      'resolve',
      () =>
        api.resolveInvestigation(investigation.investigation_id, {
          outcome: resolveOutcome,
          findings: cleanFindings || null,
          author: resolveAuthorInput.trim() || null,
        }),
      `Case INV-${investigation.investigation_id} resolved (${resolveOutcome}); linked alert updated to ${expectedAlertStatus}.`,
      () => setResolveFindingsInput('')
    );
  };

  const linkedAlert = investigation?.alert ?? null;
  const linkedTx = linkedAlert?.transaction ?? null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/80 backdrop-blur-sm">
      {/* Backdrop */}
      <div
        className="flex-1"
        onClick={() => {
          if (activeAction === null) onClose();
        }}
        aria-hidden="true"
      />

      {/* Slide-over Workspace Panel */}
      <aside
        aria-label={`Investigation Workspace #${investigationId}`}
        className="w-full max-w-3xl bg-slate-900 border-l border-slate-800 h-full overflow-y-auto shadow-2xl flex flex-col"
      >
        {/* Top Sticky Header */}
        <div className="sticky top-0 z-10 px-6 py-4 bg-slate-900/95 backdrop-blur-md border-b border-slate-800 flex items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-lg font-bold text-white font-mono">
                INV-{investigationId}
              </h2>
              {investigation && (
                <>
                  <InvestigationStatusBadge status={investigation.status} />
                  <InvestigationOutcomeBadge outcome={investigation.outcome} />
                </>
              )}
            </div>
            {investigation && (
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
                <span>
                  Assignee:{' '}
                  <strong className="text-slate-200">
                    {investigation.assigned_to || 'Unassigned'}
                  </strong>
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                  Created: {new Date(investigation.created_at).toLocaleString()}
                </span>
                <span>
                  Updated: {new Date(investigation.updated_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => loadDetails(investigationId, true)}
              disabled={detailLoading || activeAction !== null}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 disabled:opacity-40"
              title="Refresh investigation details"
            >
              <RefreshCw className={`w-4 h-4 ${detailLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={activeAction !== null}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 disabled:opacity-40"
              aria-label="Close investigation workspace"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Workspace Body */}
        <div className="p-6 space-y-6 flex-1">
          {detailLoading && !investigation ? (
            <LoadingSpinner label="Loading investigation case file..." />
          ) : detailError && !investigation ? (
            <ErrorMessage
              title="Unable to Load Case File"
              message={detailError}
              onRetry={() => loadDetails(investigationId, true)}
            />
          ) : investigation ? (
            <>
              {/* Non-destructive Refresh Error Banner */}
              {detailError && (
                <ErrorMessage
                  title="Refresh Failed"
                  message={detailError}
                  onRetry={() => loadDetails(investigationId, true)}
                />
              )}

              {/* Action Feedback Banner */}
              {feedback && (
                <div
                  role="status"
                  className={`p-3.5 rounded-xl border text-xs flex items-start justify-between gap-3 ${
                    feedback.type === 'error'
                      ? 'bg-rose-950/50 border-rose-800/70 text-rose-200'
                      : 'bg-emerald-950/50 border-emerald-800/70 text-emerald-200'
                  }`}
                >
                  <span>{feedback.message}</span>
                  <button
                    type="button"
                    onClick={() => setFeedback(null)}
                    className="text-slate-400 hover:text-white shrink-0"
                    aria-label="Dismiss message"
                  >
                    ✕
                  </button>
                </div>
              )}

              {/* Terminal Case Lock Banner */}
              {isTerminal && (
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 flex items-start gap-3 text-xs text-slate-300">
                  <Lock className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold text-white">
                      Case Closed in Terminal State ({normalizedStatus})
                    </p>
                    <p className="text-slate-400">
                      This investigation is immutable. Recorded outcome:{' '}
                      <strong className="text-slate-200">
                        {investigation.outcome || 'None (Legacy CLOSED)'}
                      </strong>
                      {linkedAlert && (
                        <>
                          {' '}
                          • Linked alert #{linkedAlert.alert_id} status:{' '}
                          <strong className="text-slate-200">{linkedAlert.status}</strong>
                        </>
                      )}
                      .
                    </p>
                  </div>
                </div>
              )}

              {/* Linked Alert & Transaction Context */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Linked Alert Card */}
                <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <AlertOctagon className="w-3.5 h-3.5 text-amber-400" />
                      Linked Fraud Alert
                    </h3>
                    {linkedAlert && (
                      <Badge
                        variant={
                          linkedAlert.status === 'OPEN'
                            ? 'warning'
                            : linkedAlert.status === 'RESOLVED'
                            ? 'success'
                            : 'neutral'
                        }
                        size="sm"
                      >
                        {linkedAlert.status}
                      </Badge>
                    )}
                  </div>

                  {linkedAlert ? (
                    <div className="space-y-1.5 text-xs">
                      <p className="text-slate-300">
                        <span className="text-slate-500">Alert ID:</span>{' '}
                        <span className="font-mono text-amber-300">
                          #{linkedAlert.alert_id}
                        </span>
                      </p>
                      <p className="text-slate-300">
                        <span className="text-slate-500">Alert Type:</span>{' '}
                        <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-200">
                          {linkedAlert.alert_type}
                        </span>
                      </p>
                      <p className="text-slate-300">
                        <span className="text-slate-500">Triggered:</span>{' '}
                        {new Date(linkedAlert.created_at).toLocaleString()}
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic">
                      Linked Alert #{investigation.alert_id} context unavailable.
                    </p>
                  )}
                </div>

                {/* Linked Transaction Card */}
                <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/90 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <CreditCard className="w-3.5 h-3.5 text-emerald-400" />
                      Linked Transaction
                    </h3>
                    {linkedTx && (
                      <Badge
                        variant={linkedTx.fraud_prediction === 1 ? 'danger' : 'success'}
                        size="sm"
                      >
                        {linkedTx.fraud_prediction === 1 ? 'Fraud Flag (1)' : 'Legit (0)'}
                      </Badge>
                    )}
                  </div>

                  {linkedTx ? (
                    <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
                      <p className="col-span-2 truncate text-slate-300">
                        <span className="text-slate-500">ID:</span>{' '}
                        <span className="font-mono text-emerald-300">
                          {linkedTx.transaction_id}
                        </span>
                      </p>
                      <p className="text-slate-300">
                        <span className="text-slate-500">Amount:</span>{' '}
                        <strong className="text-white">
                          {formatCurrencyINR(linkedTx.amount)}
                        </strong>
                      </p>
                      <p className="text-slate-300 truncate">
                        <span className="text-slate-500">Customer:</span>{' '}
                        {linkedTx.customer_id}
                      </p>
                      <p className="text-slate-300 capitalize">
                        <span className="text-slate-500">Category:</span>{' '}
                        {linkedTx.merchant_category}
                      </p>
                      <p className="text-slate-300 flex items-center gap-1 truncate">
                        <MapPin className="w-3 h-3 text-slate-500 shrink-0" />
                        {linkedTx.location}
                      </p>
                      <p className="text-slate-300">
                        <span className="text-slate-500">Method:</span>{' '}
                        {linkedTx.payment_method}
                      </p>
                      <p className="text-slate-300 truncate">
                        <span className="text-slate-500">Device:</span>{' '}
                        <span className="font-mono">{linkedTx.device_id}</span>
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic">
                      Transaction context unavailable.
                    </p>
                  )}
                </div>
              </div>

              {/* Start Investigation Banner when OPEN */}
              {isOpen && (
                <div className="p-4 rounded-xl bg-sky-950/30 border border-sky-800/50 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-sky-200 flex items-center gap-1.5">
                        <Play className="w-4 h-4 text-sky-400" />
                        Start Investigation (OPEN → IN_PROGRESS)
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Move this case into active review before resolving. Current assignee (
                        <strong className="text-slate-300">
                          {investigation.assigned_to || 'Unassigned'}
                        </strong>
                        ) will be preserved.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleStartInvestigation}
                      disabled={activeAction !== null}
                      className="px-4 py-2 text-xs font-medium bg-sky-600 hover:bg-sky-500 text-white rounded-lg inline-flex items-center gap-1.5 shrink-0 disabled:opacity-50"
                    >
                      <Play className="w-3.5 h-3.5" />
                      {activeAction === 'start' ? 'Starting...' : 'Start Investigation'}
                    </button>
                  </div>

                  <input
                    type="text"
                    value={startNoteInput}
                    onChange={(e) => setStartNoteInput(e.target.value)}
                    placeholder="Optional kickoff note (e.g. Verifying device fingerprint & velocity)..."
                    className="w-full px-3 py-2 bg-slate-950/90 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
                  />
                </div>
              )}

              {/* Analyst Assignment Controls (Mutable Only) */}
              {!isTerminal && (
                <form
                  onSubmit={handleAssignSubmit}
                  className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                      <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                      Analyst Assignment
                    </h3>
                    <span className="text-[11px] text-slate-500">
                      Current: {investigation.assigned_to || 'Unassigned'}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] text-slate-400 mb-1">
                        Analyst Name / ID (max 100 chars)
                      </label>
                      <input
                        type="text"
                        value={assigneeInput}
                        onChange={(e) => setAssigneeInput(e.target.value)}
                        maxLength={100}
                        placeholder="e.g. fraud_analyst_01"
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] text-slate-400 mb-1">
                        Optional Assignment Audit Note
                      </label>
                      <input
                        type="text"
                        value={assignNoteInput}
                        onChange={(e) => setAssignNoteInput(e.target.value)}
                        placeholder="Reason for assignment or handoff..."
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={handleUnassign}
                      disabled={activeAction !== null || !investigation.assigned_to}
                      className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg inline-flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <UserMinus className="w-3.5 h-3.5" />
                      {activeAction === 'unassign' ? 'Clearing...' : 'Unassign'}
                    </button>
                    <button
                      type="submit"
                      disabled={activeAction !== null}
                      className="px-3.5 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg inline-flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      {activeAction === 'assign' ? 'Saving...' : 'Assign Analyst'}
                    </button>
                  </div>
                </form>
              )}

              {/* Timestamped Findings & Notes Timeline */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-sky-400" />
                    Investigation Timeline & Findings
                  </h3>
                  <span className="text-[11px] text-slate-500">
                    {investigation.notes?.length || 0}{' '}
                    {(investigation.notes?.length || 0) === 1 ? 'entry' : 'entries'}
                  </span>
                </div>

                {investigation.notes && investigation.notes.length > 0 ? (
                  <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                    {investigation.notes.map((entry, idx) => (
                      <div
                        key={`${entry.timestamp || 'legacy'}-${idx}`}
                        className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80 space-y-1"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                          <span className="font-mono">
                            {entry.timestamp
                              ? new Date(entry.timestamp).toLocaleString()
                              : 'Legacy Findings Record'}
                          </span>
                          {entry.author && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                              by: {entry.author}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
                          {entry.content}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : investigation.findings ? (
                  <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80 text-xs text-slate-200 whitespace-pre-wrap">
                    {investigation.findings}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic">
                    No investigative notes or findings recorded yet.
                  </p>
                )}

                {/* Add Note Form (Mutable Only) */}
                {!isTerminal && (
                  <form
                    onSubmit={handleAddNoteSubmit}
                    className="pt-3 border-t border-slate-800/80 space-y-2.5"
                  >
                    <label className="block text-xs font-medium text-slate-300">
                      Append Timestamped Note
                    </label>
                    <textarea
                      rows={3}
                      value={noteInput}
                      onChange={(e) => setNoteInput(e.target.value)}
                      placeholder="Document evidence, cardholder verification call results, IP/device correlation..."
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                    />
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <input
                        type="text"
                        value={noteAuthorInput}
                        onChange={(e) => setNoteAuthorInput(e.target.value)}
                        maxLength={100}
                        placeholder={`Optional author (defaults to ${
                          investigation.assigned_to || 'unassigned'
                        })`}
                        className="sm:w-64 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                      />
                      <button
                        type="submit"
                        disabled={activeAction !== null}
                        className="px-3.5 py-1.5 text-xs font-medium text-white bg-sky-600 hover:bg-sky-500 rounded-lg inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
                      >
                        <MessageSquarePlus className="w-3.5 h-3.5" />
                        {activeAction === 'note' ? 'Appending...' : 'Add Note'}
                      </button>
                    </div>
                  </form>
                )}
              </div>

              {/* Resolve Investigation Section */}
              {!isTerminal && (
                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      Resolve Case & Synchronize Alert
                    </h3>
                  </div>

                  {!isInProgress ? (
                    <p className="text-xs text-amber-300/90 bg-amber-950/30 border border-amber-800/50 rounded-lg p-3">
                      Start this investigation (
                      <span className="font-semibold font-mono">OPEN → IN_PROGRESS</span>)
                      before recording a final outcome and resolving the case.
                    </p>
                  ) : (
                    <form onSubmit={handleResolveSubmit} className="space-y-3">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <button
                          type="button"
                          onClick={() => setResolveOutcome('CONFIRMED_FRAUD')}
                          className={`p-3 rounded-lg border text-left transition-colors ${
                            resolveOutcome === 'CONFIRMED_FRAUD'
                              ? 'bg-rose-950/50 border-rose-500/70 text-rose-200'
                              : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex items-center gap-2 text-xs font-semibold">
                            <ShieldAlert className="w-4 h-4 text-rose-400" />
                            CONFIRMED FRAUD
                          </div>
                          <p className="text-[11px] opacity-80 mt-1">
                            Sets linked alert status to <strong>RESOLVED</strong>.
                          </p>
                        </button>

                        <button
                          type="button"
                          onClick={() => setResolveOutcome('LEGITIMATE')}
                          className={`p-3 rounded-lg border text-left transition-colors ${
                            resolveOutcome === 'LEGITIMATE'
                              ? 'bg-emerald-950/50 border-emerald-500/70 text-emerald-200'
                              : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex items-center gap-2 text-xs font-semibold">
                            <ShieldCheck className="w-4 h-4 text-emerald-400" />
                            LEGITIMATE
                          </div>
                          <p className="text-[11px] opacity-80 mt-1">
                            Sets linked alert status to <strong>DISMISSED</strong>.
                          </p>
                        </button>
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-slate-300 mb-1">
                          Final Resolution Findings{' '}
                          {!hasExistingFindingsOrNotes ? (
                            <span className="text-rose-400">*</span>
                          ) : (
                            <span className="text-slate-500 font-normal">
                              (optional — prior timeline notes satisfy findings requirement)
                            </span>
                          )}
                        </label>
                        <textarea
                          rows={3}
                          value={resolveFindingsInput}
                          onChange={(e) => setResolveFindingsInput(e.target.value)}
                          placeholder="Summarize final fraud determination rationale and evidence..."
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                        />
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <input
                          type="text"
                          value={resolveAuthorInput}
                          onChange={(e) => setResolveAuthorInput(e.target.value)}
                          maxLength={100}
                          placeholder={`Optional resolving author (defaults to ${
                            investigation.assigned_to || 'unassigned'
                          })`}
                          className="sm:w-64 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                        />
                        <button
                          type="submit"
                          disabled={activeAction !== null}
                          className="px-4 py-2 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          {activeAction === 'resolve'
                            ? 'Resolving Case...'
                            : 'Confirm & Resolve Case'}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
};
