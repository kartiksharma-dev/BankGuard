import React from 'react';

interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Loading...',
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  }[size];

  return (
    <div className="flex flex-col items-center justify-center p-8 space-y-3" role="status" aria-live="polite">
      <div
        className={`${sizeClasses} border-slate-700 border-t-emerald-500 rounded-full animate-spin`}
        aria-hidden="true"
      />
      {label && <p className="text-sm text-slate-400 font-medium">{label}</p>}
    </div>
  );
};
