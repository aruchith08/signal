import React from 'react';
import { clsx } from 'clsx';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, leftIcon, className, ...props }, ref) => {
    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {leftIcon && (
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            className={clsx(
              'w-full rounded-lg border bg-[#090D16] px-3 py-2 text-sm text-slate-100 placeholder-slate-500 transition-colors focus:outline-none focus:ring-1',
              leftIcon ? 'pl-9' : 'pl-3',
              error
                ? 'border-rose-700/80 focus:border-rose-500 focus:ring-rose-500/20'
                : 'border-slate-750 border-slate-700/80 focus:border-emerald-500 focus:ring-emerald-500/20',
              className
            )}
            {...props}
          />
        </div>
        {error && <p className="text-xs text-rose-400">{error}</p>}
        {hint && !error && <p className="text-[11px] text-slate-500">{hint}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
