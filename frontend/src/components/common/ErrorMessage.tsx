import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorMessageProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = 'An error occurred',
  message,
  onRetry,
}) => {
  return (
    <div
      role="alert"
      className="p-5 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 my-4"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-rose-400 mt-0.5 flex-shrink-0" aria-hidden="true" />
        <div>
          <h4 className="font-semibold text-rose-300 text-sm">{title}</h4>
          <p className="text-sm text-rose-200/90 mt-0.5">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          type="button"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-200 bg-rose-900/60 hover:bg-rose-800/80 border border-rose-700/60 rounded-lg transition-colors flex-shrink-0"
        >
          <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
