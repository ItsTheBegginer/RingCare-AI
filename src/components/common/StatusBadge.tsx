import React from 'react';
import { EventStatus } from '../../types/events';
import { CheckCircle2, AlertTriangle, CheckCheck, XCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: EventStatus;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const isSm = size === 'sm';

  switch (status) {
    case 'review':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium tabular-nums ${
            isSm ? 'text-xs' : 'text-xs'
          } text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md`}
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
          <span>Requires Review</span>
        </span>
      );
    case 'normal':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium tabular-nums ${
            isSm ? 'text-xs' : 'text-xs'
          } text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md`}
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
          <span>Normal</span>
        </span>
      );
    case 'acknowledged':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium tabular-nums ${
            isSm ? 'text-xs' : 'text-xs'
          } text-sky-800 bg-sky-50 border border-sky-200 px-2 py-0.5 rounded-md`}
        >
          <CheckCheck className="w-3.5 h-3.5 text-sky-600 shrink-0" />
          <span>Acknowledged</span>
        </span>
      );
    case 'dismissed':
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-medium tabular-nums ${
            isSm ? 'text-xs' : 'text-xs'
          } text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md`}
        >
          <XCircle className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span>Dismissed</span>
        </span>
      );
  }
};
