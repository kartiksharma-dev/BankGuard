import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No records found',
  description,
  actionText,
  onAction,
  icon,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center bg-slate-900/40 border border-slate-800/80 rounded-xl my-4">
      <div className="w-12 h-12 rounded-full bg-slate-800/60 flex items-center justify-center text-slate-400 mb-3">
        {icon || <Inbox className="w-6 h-6" aria-hidden="true" />}
      </div>
      <h4 className="text-base font-semibold text-slate-200">{title}</h4>
      <p className="text-sm text-slate-400 max-w-sm mt-1">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          type="button"
          className="mt-4 px-4 py-2 text-xs font-medium text-emerald-400 bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-800/60 rounded-lg transition-colors"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
