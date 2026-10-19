import React, { useState } from 'react';
import { Event, Camera, EventStatus } from '../types/events';
import { StatusBadge } from '../components/common/StatusBadge';
import { SeverityBadge } from '../components/common/SeverityBadge';
import { EmptyState, LoadingSkeleton, ErrorState } from '../components/common/FeedbackStates';
import {
  Clock3,
  Video,
  User,
  Activity,
  CheckCircle2,
  XCircle,
  Eye,
  Filter,
  CheckCheck,
  AlertTriangle,
} from 'lucide-react';

interface ActivityPageProps {
  events: Event[];
  cameras: Camera[];
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
  onSelectEvent: (event: Event) => void;
  onQuickAcknowledge: (id: string) => Promise<void>;
  onQuickDismiss: (id: string) => Promise<void>;
}

export const ActivityPage: React.FC<ActivityPageProps> = ({
  events,
  cameras,
  isLoading,
  error,
  onRetry,
  onSelectEvent,
  onQuickAcknowledge,
  onQuickDismiss,
}) => {
  const [statusFilter, setStatusFilter] = useState<'all' | EventStatus>('all');
  const [selectedCameraId, setSelectedCameraId] = useState<string>('all');

  const filteredEvents = events.filter(e => {
    if (statusFilter !== 'all' && e.aiStatus !== statusFilter) return false;
    if (selectedCameraId !== 'all' && e.cameraId !== selectedCameraId) return false;
    return true;
  });

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return {
        time: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        date: d.toLocaleDateString([], { month: 'short', day: 'numeric' }),
      };
    } catch {
      return { time: iso, date: 'Today' };
    }
  };

  return (
    <div className="space-y-6">
      {error && (
        <ErrorState
          title="Activity Timeline Connection Issue"
          description={error}
          actionText="Retry Timeline"
          onAction={onRetry}
        />
      )}

      {/* Header and Filter Controls */}
      <div className="p-4 sm:p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700 shadow-2xs">
            <Clock3 className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Daily Activity Timeline</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Sequential chronology of resident routines and computer-vision detections
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
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
                onClick={() => setStatusFilter(tab.id)}
                className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                  statusFilter === tab.id
                    ? 'bg-white text-slate-900 font-semibold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Camera Filter Dropdown */}
          <select
            value={selectedCameraId}
            onChange={e => setSelectedCameraId(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-lg bg-slate-50 border border-slate-200/90 text-slate-800 focus:outline-none focus:border-teal-500 focus:bg-white transition-colors"
          >
            <option value="all">All Cameras ({cameras.length})</option>
            {cameras.map(c => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Timeline List or Loading */}
      {isLoading ? (
        <div className="p-4 bg-white rounded-xl border border-slate-200/80">
          <LoadingSkeleton rows={6} />
        </div>
      ) : filteredEvents.length === 0 ? (
        <EmptyState
          title="No timeline events found"
          description="There are no events matching your active camera and status filters."
          actionText="Reset Filters"
          onAction={() => {
            setStatusFilter('all');
            setSelectedCameraId('all');
          }}
        />
      ) : (
        <div className="relative pl-6 sm:pl-8 space-y-6 before:absolute before:left-3 sm:before:left-4 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
          {filteredEvents.map(event => {
            const { time, date } = formatTime(event.timestamp);
            const isReview = event.aiStatus === 'review';

            return (
              <div key={event.id} className="relative group">
                {/* Timeline Dot Marker */}
                <div
                  className={`absolute -left-6 sm:-left-8 top-3.5 w-3 h-3 rounded-full border-2 transition-transform group-hover:scale-125 ${
                    isReview
                      ? 'bg-amber-400 border-amber-600 ring-4 ring-amber-500/20'
                      : event.aiStatus === 'acknowledged'
                      ? 'bg-sky-500 border-sky-600 ring-2 ring-sky-500/20'
                      : 'bg-emerald-500 border-emerald-600'
                  }`}
                />

                {/* Timeline Event Card */}
                <div
                  onClick={() => onSelectEvent(event)}
                  tabIndex={0}
                  role="button"
                  onKeyDown={e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      onSelectEvent(event);
                    }
                  }}
                  className={`p-4 sm:p-4.5 rounded-xl border transition-all cursor-pointer shadow-xs ${
                    isReview
                      ? 'bg-gradient-to-r from-amber-50/40 via-amber-50/15 to-white border-amber-200/90 border-l-4 border-l-amber-500 hover:border-amber-300 hover:shadow-sm'
                      : event.aiStatus === 'acknowledged'
                      ? 'bg-white border-slate-200/80 border-l-4 border-l-sky-500 hover:border-slate-300 hover:shadow-sm'
                      : 'bg-white border-slate-200/80 border-l-4 border-l-emerald-500 hover:border-slate-300 hover:shadow-sm'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200/80 tabular-nums">
                        {time}
                      </span>
                      <span className="text-slate-400">·</span>
                      <span className="font-semibold text-xs text-slate-900">
                        {event.cameraName}
                      </span>
                      <span className="text-[10px] text-slate-600 font-mono px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 capitalize">
                        {event.eventType.replace('_', ' ')}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <StatusBadge status={event.aiStatus} size="sm" />
                      <SeverityBadge severity={event.severity} />
                    </div>
                  </div>

                  {/* Body Info */}
                  <div className="mt-2.5 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                    <div className="flex-1">
                      <p className="text-slate-800 leading-relaxed font-normal">
                        {event.summary}
                      </p>

                      <div className="flex flex-wrap items-center gap-3 mt-2 text-[11px] text-slate-500 font-mono">
                        <span className="flex items-center gap-1 text-slate-700 font-medium">
                          <User className="w-3 h-3 text-teal-600" />
                          Person detected: {event.personDetected ? 'Yes' : 'No'}
                        </span>
                        <span>·</span>
                        <span>Motion score: {Math.round(event.motionScore * 100)}%</span>
                        {event.stationaryDuration > 0 && (
                          <>
                            <span>·</span>
                            <span className="text-amber-800 font-semibold">
                              Still: {event.stationaryDuration.toFixed(1)}s
                            </span>
                          </>
                        )}
                        <span>·</span>
                        <span className="text-slate-600 italic font-sans">
                          {event.aiAssessment.recommendedAction}
                        </span>
                      </div>
                    </div>

                    {/* Quick Action Buttons */}
                    <div
                      className="flex items-center gap-1.5 self-end sm:self-center shrink-0"
                      onClick={e => e.stopPropagation()}
                    >
                      {event.aiStatus === 'review' ? (
                        <>
                          <button
                            onClick={() => onQuickAcknowledge(event.id)}
                            className="px-2.5 py-1 text-xs font-semibold text-teal-900 bg-teal-50 hover:bg-teal-100 border border-teal-200/90 rounded transition-colors shadow-2xs"
                          >
                            Acknowledge
                          </button>
                          <button
                            onClick={() => onQuickDismiss(event.id)}
                            className="px-2 py-1 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors"
                          >
                            Dismiss
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => onSelectEvent(event)}
                          className="px-2.5 py-1 text-xs text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/80 rounded transition-colors inline-flex items-center gap-1"
                        >
                          <Eye className="w-3.5 h-3.5 text-slate-500" />
                          <span>Inspect</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
