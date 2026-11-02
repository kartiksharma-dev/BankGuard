import React from 'react';

export type BadgeVariant =
  | 'success'
  | 'danger'
  | 'warning'
  | 'info'
  | 'neutral'
  | 'purple';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
}) => {
  const variantStyles: Record<BadgeVariant, string> = {
    success: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    danger: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    warning: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    info: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    purple: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    neutral: 'bg-slate-700/30 text-slate-300 border-slate-600/40',
  };

  const sizeStyles = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs font-medium',
  }[size];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-medium tracking-wide ${sizeStyles} ${variantStyles[variant]}`}
    >
      {children}
    </span>
  );
};
