import React from 'react';
import { HelpCircle } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  definition?: string;
  icon: React.ReactNode;
  variant?: 'default' | 'danger' | 'warning' | 'success';
  loading?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  definition,
  icon,
  variant = 'default',
  loading = false,
}) => {
  const borderVariants = {
    default: 'border-slate-800/80 hover:border-slate-700/90',
    danger: 'border-rose-900/40 hover:border-rose-700/60 bg-gradient-to-br from-slate-900/90 via-slate-900 to-rose-950/20',
    warning: 'border-amber-900/40 hover:border-amber-700/60 bg-gradient-to-br from-slate-900/90 via-slate-900 to-amber-950/20',
    success: 'border-emerald-900/40 hover:border-emerald-700/60 bg-gradient-to-br from-slate-900/90 via-slate-900 to-emerald-950/20',
  }[variant];

  const iconVariants = {
    default: 'bg-slate-800/60 text-slate-300',
    danger: 'bg-rose-950/60 text-rose-400 border border-rose-800/50',
    warning: 'bg-amber-950/60 text-amber-400 border border-amber-800/50',
    success: 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50',
  }[variant];

  return (
    <div
      className={`relative p-5 rounded-xl bg-slate-900/70 border backdrop-blur-sm transition-all duration-150 ${borderVariants}`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            {title}
          </span>
          {definition && (
            <div className="relative group cursor-pointer" tabIndex={0} aria-label={definition}>
              <HelpCircle className="w-3.5 h-3.5 text-slate-500 hover:text-slate-300" />
              <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:block group-focus:block w-48 p-2 bg-slate-800 text-slate-200 text-xs rounded shadow-lg border border-slate-700 z-20 pointer-events-none">
                {definition}
              </div>
            </div>
          )}
        </div>
        <div className={`p-2 rounded-lg ${iconVariants}`}>{icon}</div>
      </div>

      <div className="mt-3">
        {loading ? (
          <div className="h-8 w-24 bg-slate-800/80 rounded animate-pulse" />
        ) : (
          <p className="text-2xl sm:text-3xl font-semibold tracking-tight text-slate-100">
            {value}
          </p>
        )}

        {subtitle && (
          <p className="mt-1 text-xs text-slate-400 truncate">
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
};
