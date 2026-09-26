import React from 'react';
import { clsx } from 'clsx';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'purple' | 'outline' | 'slate';
  size?: 'xs' | 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'sm',
  className,
  ...props
}) => {
  const sizeClasses = {
    xs: 'px-1.5 py-0.5 text-[10px] leading-3 font-medium',
    sm: 'px-2 py-0.5 text-xs font-medium',
    md: 'px-2.5 py-1 text-xs font-semibold',
  };

  const variantClasses = {
    default: 'bg-slate-800/80 text-slate-300 border border-slate-700/60',
    slate: 'bg-slate-900 text-slate-400 border border-slate-800',
    success: 'bg-emerald-950/60 text-emerald-300 border border-emerald-700/40',
    warning: 'bg-amber-950/60 text-amber-300 border border-amber-700/40',
    error: 'bg-rose-950/60 text-rose-300 border border-rose-700/40',
    info: 'bg-sky-950/60 text-sky-300 border border-sky-700/40',
    purple: 'bg-purple-950/60 text-purple-300 border border-purple-700/40',
    outline: 'bg-transparent text-slate-300 border border-slate-700',
  };

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-md transition-colors',
        sizeClasses[size],
        variantClasses[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
