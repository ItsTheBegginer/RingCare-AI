import React, { useState } from 'react';
import { Event, EventStatus } from '../../types/events';
import { StatusBadge } from '../common/StatusBadge';
import { SeverityBadge } from '../common/SeverityBadge';
import { LoadingSkeleton, EmptyState } from '../common/FeedbackStates';
import {
  Search,
  CheckCircle2,
  XCircle,
  Eye,
  Filter,
  User,
  Activity,
  ArrowRight,
} from 'lucide-react';

interface RecentEventsProps {
  events: Event[];
  isLoading: boolean;
  onSelectEvent: (event: Event) => void;
  onQuickAcknowledge: (id: string) => Promise<void>;
  onQuickDismiss: (id: string) => Promise<void>;
  activeStatusFilter: 'all' | EventStatus;
  onChangeStatusFilter: (status: 'all' | EventStatus) => void;
  onViewAllClick?: () => void;
  maxDisplay?: number;
}

export const RecentEvents: React.FC<RecentEventsProps> = ({
  events,
  isLoading,
  onSelectEvent,
  onQuickAcknowledge,
  onQuickDismiss,
  activeStatusFilter,
  onChangeStatusFilter,
  onViewAllClick,
  maxDisplay,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [actionInProgressId, setActionInProgressId] = useState<string | null>(null);

  // Filter events by search query
  const filteredEvents = events.filter(e => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      e.cameraName.toLowerCase().includes(q) ||
      e.summary.toLowerCase().includes(q) ||
      e.eventType.toLowerCase().includes(q) ||
      e.aiStatus.toLowerCase().includes(q)
    );
  });

  const displayList = maxDisplay ? filteredEvents.slice(0, maxDisplay) : filteredEvents;

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  };

  const handleQuickAck = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setActionInProgressId(id);
    try {
      await onQuickAcknowledge(id);
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleQuickDismiss = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setActionInProgressId(id);
    try {
      await onQuickDismiss(id);
    } finally {
      setActionInProgressId(null);
    }
  };

  return (
    <div className="rounded-xl bg-white border border-slate-200/80 shadow-sm overflow-hidden">
      {/* Top Header & Filter Bar */}
      <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900">Recent Triage Events</h3>
            <span className="text-[10px] font-mono text-teal-800 bg-teal-50 border border-teal-200/80 px-2 py-0.5 rounded-md font-medium">
              Live Stream
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Click any row to inspect optical computer vision & AI assessment rationale
          </p>
        </div>

        {/* Filter controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search box */}
          <div className="relative flex-1 sm:w-56">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search camera or summary..."
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-slate-50 border border-slate-200/90 text-slate-800 placeholder-slate-400 focus:outline-none focus:border-teal-500 focus:bg-white transition-colors"
            />
          </div>

          {/* Status Segmented Buttons */}
          <div className="flex items-center p-0.5 bg-slate-100 border border-slate-200/60 rounded-lg text-xs">
            {(
              [
                { id: 'all', label: 'All' },
                { id: 'review', label: 'Review' },
                { id: 'normal', label: 'Normal' },
                { id: 'acknowledged', label: 'Acknowledged' },
              ] as const
            ).map(tab => (
              <button
                key={tab.id}
                onClick={() => onChangeStatusFilter(tab.id)}
                className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                  activeStatusFilter === tab.id
                    ? 'bg-white text-slate-900 font-semibold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {onViewAllClick && (
            <button
              onClick={onViewAllClick}
              className="hidden lg:flex items-center gap-1 text-xs text-teal-700 hover:text-teal-800 font-semibold ml-1 transition-colors"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Events Table / List */}
      {isLoading ? (
        <div className="p-4">
          <LoadingSkeleton rows={5} />
        </div>
      ) : displayList.length === 0 ? (
        <div className="p-6">
          <EmptyState
            title="No events found"
            description="No triage events match the selected status filter or search query."
            actionText="Clear Filters"
            onAction={() => {
              setSearchQuery('');
              onChangeStatusFilter('all');
            }}
          />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] text-slate-500 font-semibold uppercase tracking-wider">
                <th className="py-2.5 px-4">Camera</th>
                <th className="py-2.5 px-3">Event Type</th>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Person</th>
                <th className="py-2.5 px-3">Motion Score</th>
                <th className="py-2.5 px-3">AI Status</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayList.map(event => {
                const isActioning = actionInProgressId === event.id;

                return (
                  <tr
                    key={event.id}
                    onClick={() => onSelectEvent(event)}
                    tabIndex={0}
                    role="button"
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        onSelectEvent(event);
                      }
                    }}
                    className={`cursor-pointer transition-colors duration-150 group ${
                      event.aiStatus === 'review'
                        ? 'bg-amber-50/35 hover:bg-amber-50/70 border-l-2 border-l-amber-500'
                        : 'hover:bg-slate-50/80'
                    }`}
                  >
                    {/* Camera */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-slate-900 group-hover:text-teal-700 transition-colors">
                          {event.cameraName}
                        </span>
                        {(event.videoStatus === 'sample' || event.source === 'ring+sample-clip') && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-50 text-amber-700 border border-amber-200/80">
                            Sample
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate max-w-xs sm:max-w-sm mt-0.5">
                        {event.summary}
                      </div>
                    </td>

                    {/* Event Type */}
                    <td className="py-3 px-3">
                      <span className="font-mono text-slate-700 capitalize">
                        {event.eventType.replace('_', ' ')}
                      </span>
                    </td>

                    {/* Timestamp */}
                    <td className="py-3 px-3 font-mono text-slate-700 tabular-nums">
                      {formatTime(event.timestamp)}
                    </td>

                    {/* Person Detected */}
                    <td className="py-3 px-3">
                      {event.personDetected ? (
                        <span className="inline-flex items-center gap-1 text-slate-700 font-medium">
                          <User className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                          <span>Yes</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">No</span>
                      )}
                    </td>

                    {/* Motion Score */}
                    <td className="py-3 px-3 font-mono tabular-nums text-slate-700">
                      <div className="flex items-center gap-2">
                        <span>{Math.round(event.motionScore * 100)}%</span>
                        <div className="w-12 h-1.5 rounded-full bg-slate-200 overflow-hidden hidden sm:block">
                          <div
                            style={{ width: `${Math.round(event.motionScore * 100)}%` }}
                            className={`h-full ${
                              event.motionScore > 0.7
                                ? 'bg-teal-600'
                                : event.motionScore > 0.4
                                ? 'bg-indigo-600'
                                : 'bg-slate-300'
                            }`}
                          />
                        </div>
                      </div>
                    </td>

                    {/* AI Status */}
                    <td className="py-3 px-3">
                      <StatusBadge status={event.aiStatus} size="sm" />
                    </td>

                    {/* Severity */}
                    <td className="py-3 px-3">
                      <SeverityBadge severity={event.severity} />
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right">
                      <div className="inline-flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
                        {event.aiStatus === 'review' ? (
                          <>
                            <button
                              onClick={e => handleQuickAck(e, event.id)}
                              disabled={isActioning}
                              title="Acknowledge event"
                              className="px-2.5 py-1 text-xs font-semibold text-teal-800 bg-teal-50 hover:bg-teal-100 border border-teal-200/90 rounded-md transition-colors disabled:opacity-50 shadow-2xs"
                            >
                              Acknowledge
                            </button>
                            <button
                              onClick={e => handleQuickDismiss(e, event.id)}
                              disabled={isActioning}
                              title="Dismiss event"
                              className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
                            >
                              <XCircle className="w-3.5 h-3.5" />
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => onSelectEvent(event)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/80 border border-slate-200/60 rounded-md transition-colors"
                          >
                            <Eye className="w-3.5 h-3.5 text-slate-500" />
                            <span>Details</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
