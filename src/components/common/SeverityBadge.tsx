import React from 'react';
import { EventSeverity } from '../../types/events';

interface SeverityBadgeProps {
  severity: EventSeverity;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  switch (severity) {
    case 'high':
      return (
        <span className="inline-flex items-center text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded uppercase tracking-wide">
          High
        </span>
      );
    case 'medium':
      return (
        <span className="inline-flex items-center text-xs font-medium text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded capitalize">
          Medium
        </span>
      );
    case 'low':
    default:
      return (
        <span className="inline-flex items-center text-xs font-medium text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded capitalize">
          Low
        </span>
      );
  }
};
