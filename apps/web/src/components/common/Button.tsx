import React from 'react';
import { clsx } from 'clsx';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  className,
  ...props
}) => {
  const sizeClasses = {
    xs: 'px-2 py-1 text-xs font-medium',
    sm: 'px-2.5 py-1.5 text-xs font-medium',
    md: 'px-3.5 py-2 text-sm font-medium',
    lg: 'px-4 py-2.5 text-base font-semibold',
  };

  const variantClasses = {
    primary:
      'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm hover:shadow-emerald-900/20 active:bg-emerald-700',
    secondary:
      'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 active:bg-slate-850',
    outline:
      'bg-transparent hover:bg-slate-800/60 text-slate-300 border border-slate-700 hover:border-slate-600 active:bg-slate-800',
    ghost:
      'bg-transparent hover:bg-slate-800/50 text-slate-400 hover:text-slate-200',
    danger:
      'bg-rose-600/90 hover:bg-rose-500 text-white shadow-sm active:bg-rose-700',
  };

  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:opacity-50 disabled:pointer-events-none cursor-pointer select-none',
        sizeClasses[size],
        variantClasses[variant],
        className
      )}
      {...props}
    >
      {loading && (
        <svg
          className="animate-spin -ml-1 mr-1 h-3.5 w-3.5 text-current"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {children}
    </button>
  );
};
