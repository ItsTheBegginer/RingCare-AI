import React from 'react';
import { Inbox } from 'lucide-react';

export const LoadingSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-14 bg-slate-100/90 border border-slate-200/80 rounded-lg flex items-center px-4 justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-slate-200" />
            <div className="space-y-1.5">
              <div className="w-32 h-3.5 bg-slate-200 rounded" />
              <div className="w-48 h-2.5 bg-slate-200/70 rounded" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-16 h-4 bg-slate-200 rounded" />
            <div className="w-20 h-5 bg-slate-200 rounded" />
            <div className="w-16 h-7 bg-slate-200 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
};

interface EmptyStateProps {
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionText,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-slate-300 rounded-xl bg-slate-50/50">
      <div className="w-12 h-12 rounded-full bg-white border border-slate-200 shadow-xs flex items-center justify-center text-slate-500 mb-4">
        <Inbox className="w-6 h-6" />
      </div>
      <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
      <p className="text-xs text-slate-500 max-w-sm mt-1 mb-4">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="px-3.5 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-xs transition-colors"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};

interface ErrorStateProps {
  title?: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Telemetry Error',
  description,
  actionText = 'Retry',
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-10 text-center border border-rose-200/90 rounded-xl bg-rose-50/40">
      <div className="w-12 h-12 rounded-full bg-white border border-rose-200 shadow-xs flex items-center justify-center text-rose-500 mb-4">
        <Inbox className="w-6 h-6 text-rose-500" />
      </div>
      <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
      <p className="text-xs text-slate-600 max-w-md mt-1 mb-4">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="px-3.5 py-1.5 text-xs font-medium text-rose-800 bg-white hover:bg-rose-50 border border-rose-300 rounded-lg shadow-xs transition-colors"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
