import React from 'react';
import { clsx } from 'clsx';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverEffect?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  hoverEffect = false,
  className,
  ...props
}) => {
  return (
    <div
      className={clsx(
        'rounded-xl border border-slate-800 bg-[#0F172A]/80 p-5 shadow-lg backdrop-blur-sm',
        hoverEffect && 'transition-all duration-200 hover:border-slate-700/80 hover:bg-[#131D33]/90 hover:shadow-xl',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
