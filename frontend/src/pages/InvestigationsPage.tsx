import React, { useEffect, useState, useCallback } from 'react';
import {
  FileSearch,
  Filter,
  Edit3,
  Calendar,
  User,
  CheckCircle,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { api } from '../services/apiClient';
import { InvestigationItem } from '../types/api';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorMessage } from '../components/common/ErrorMessage';
import { EmptyState } from '../components/common/EmptyState';

export const InvestigationsPage: React.FC = () => {
  const [investigations, setInvestigations] = useState<InvestigationItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Edit/Update Investigation Modal State
  const [editingInv, setEditingInv] = useState<InvestigationItem | null>(null);
  const [statusInput, setStatusInput] = useState<string>('IN_PROGRESS');
  const [assignedToInput, setAssignedToInput] = useState<string>('');
  const [findingsInput, setFindingsInput] = useState<string>('');
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [updateFeedback, setUpdateFeedback] = useState<string | null>(null);

  const fetchInvestigations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const statusParam = statusFilter !== 'all' ? statusFilter : undefined;
      const res = await api.getInvestigations({
        status: statusParam,
        limit: 50,
      });
      setInvestigations(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve investigations.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchInvestigations();
  }, [fetchInvestigations]);

  const openEditModal = (inv: InvestigationItem) => {
    setEditingInv(inv);
    setStatusInput(inv.status);
    setAssignedToInput(inv.assigned_to || '');
    setFindingsInput(inv.findings || '');
    setUpdateFeedback(null);
  };

  const handleUpdateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingInv) return;
    setIsUpdating(true);
    setUpdateFeedback(null);
    try {
      await api.updateInvestigation(editingInv.investigation_id, {
        status: statusInput.trim() || undefined,
        assigned_to: assignedToInput.trim() || null,
        findings: findingsInput.trim() || null,
      });
      setUpdateFeedback('Investigation updated successfully!');
      setTimeout(() => {
        setEditingInv(null);
        setUpdateFeedback(null);
        fetchInvestigations();
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update investigation.';
      setUpdateFeedback(`Error: ${msg}`);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Investigations</h1>
        <p className="text-sm text-slate-400 mt-1">
          Review case files, log investigative findings, and update case statuses for suspicious fraud alerts.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="p-4 bg-slate-900/70 border border-slate-800/80 rounded-xl flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 bg-slate-950/80 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="all">All Investigations</option>
            <option value="OPEN">Open</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="CLOSED">Closed</option>
          </select>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <ErrorMessage
          title="Investigations Query Failed"
          message={error}
          onRetry={fetchInvestigations}
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
              statusFilter !== 'all'
                ? 'Try selecting a different status filter.'
                : 'No investigations are active. You can initiate an investigation from the Alerts page.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/70 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">Case ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Alert ID</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Assigned Analyst</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Findings / Summary</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Last Updated</th>
                  <th scope="col" className="px-4 py-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {investigations.map((inv) => (
                  <tr key={inv.investigation_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-slate-200">
                      INV-{inv.investigation_id}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-amber-400">
                      Alert #{inv.alert_id}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-300">
                      <span className="flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5 text-slate-500" />
                        {inv.assigned_to || <span className="text-slate-500 italic">Unassigned</span>}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {inv.status.toUpperCase() === 'OPEN' ? (
                        <Badge variant="warning" size="sm">
                          <Clock className="w-3 h-3" />
                          OPEN
                        </Badge>
                      ) : inv.status.toUpperCase() === 'IN_PROGRESS' ? (
                        <Badge variant="info" size="sm">
                          <AlertCircle className="w-3 h-3" />
                          IN PROGRESS
                        </Badge>
                      ) : (
                        <Badge variant="success" size="sm">
                          <CheckCircle className="w-3 h-3" />
                          CLOSED
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400 max-w-xs truncate">
                      {inv.findings || <span className="text-slate-600 italic">No notes logged yet</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-slate-500" />
                        {new Date(inv.updated_at).toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => openEditModal(inv)}
                        type="button"
                        className="px-2.5 py-1 text-xs font-medium text-emerald-300 bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-800/50 rounded-lg transition-colors inline-flex items-center gap-1"
                        title="Update findings and status"
                      >
                        <Edit3 className="w-3 h-3" />
                        Update
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Investigation Modal */}
      {editingInv && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Edit3 className="w-5 h-5 text-emerald-400" />
                Update Investigation Case #{editingInv.investigation_id}
              </h3>
              <button
                onClick={() => setEditingInv(null)}
                className="text-slate-400 hover:text-slate-200 text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUpdateSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Status
                  </label>
                  <select
                    value={statusInput}
                    onChange={(e) => setStatusInput(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="OPEN">OPEN</option>
                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                    <option value="CLOSED">CLOSED</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Assigned Analyst
                  </label>
                  <input
                    type="text"
                    value={assignedToInput}
                    onChange={(e) => setAssignedToInput(e.target.value)}
                    placeholder="Analyst name or ID"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Findings & Investigation Notes
                </label>
                <textarea
                  rows={4}
                  value={findingsInput}
                  onChange={(e) => setFindingsInput(e.target.value)}
                  placeholder="Document risk verification findings, evidence, customer contact results, or decision rationale..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>

              {updateFeedback && (
                <p className={`text-xs ${updateFeedback.startsWith('Error') ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {updateFeedback}
                </p>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingInv(null)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdating}
                  className="px-4 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg disabled:opacity-50"
                >
                  {isUpdating ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
