import React, { useState } from 'react';
import { Event, Camera, EventStatus, EventSeverity } from '../types/events';
import { RecentEvents } from '../components/dashboard/RecentEvents';
import { ErrorState } from '../components/common/FeedbackStates';
import { Radio, Filter, RefreshCw, Zap } from 'lucide-react';

interface LiveEventsPageProps {
  events: Event[];
  cameras: Camera[];
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
  onSelectEvent: (event: Event) => void;
  onQuickAcknowledge: (id: string) => Promise<void>;
  onQuickDismiss: (id: string) => Promise<void>;
  onSimulateEvent: () => void;
  isSimulating?: boolean;
}

export const LiveEventsPage: React.FC<LiveEventsPageProps> = ({
  events,
  cameras,
  isLoading,
  error,
  onRetry,
  onSelectEvent,
  onQuickAcknowledge,
  onQuickDismiss,
  onSimulateEvent,
  isSimulating,
}) => {
  const [statusFilter, setStatusFilter] = useState<'all' | EventStatus>('all');
  const [selectedCameraId, setSelectedCameraId] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<'all' | EventSeverity>('all');

  // Filter events based on all criteria
  const filteredEvents = events.filter(e => {
    if (statusFilter !== 'all' && e.aiStatus !== statusFilter) return false;
    if (selectedCameraId !== 'all' && e.cameraId !== selectedCameraId) return false;
    if (selectedSeverity !== 'all' && e.severity !== selectedSeverity) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      {error && (
        <ErrorState
          title="Live Events Stream Issue"
          description={error}
          actionText="Retry Connection"
          onAction={onRetry}
        />
      )}

      {/* Top Filter & Stream Bar */}
      <div className="p-4 sm:p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700 shadow-2xs">
            <Radio className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Live Event Triage Feed</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Aggregated optical flow events prioritized by AI urgency
            </p>
          </div>
        </div>

        {/* Camera and Severity Dropdowns */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Camera filter */}
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

          {/* Severity filter */}
          <select
            value={selectedSeverity}
            onChange={e => setSelectedSeverity(e.target.value as 'all' | EventSeverity)}
            className="px-3 py-1.5 text-xs rounded-lg bg-slate-50 border border-slate-200/90 text-slate-800 focus:outline-none focus:border-teal-500 focus:bg-white transition-colors"
          >
            <option value="all">All Severities</option>
            <option value="high">High Severity Only</option>
            <option value="medium">Medium Severity</option>
            <option value="low">Low Severity</option>
          </select>

          {/* Inject Mock Event Button */}
          <button
            onClick={onSimulateEvent}
            disabled={isSimulating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-teal-800 bg-teal-50 hover:bg-teal-100 border border-teal-200/90 rounded-lg transition-colors disabled:opacity-50 shadow-2xs"
          >
            <Zap className="w-3.5 h-3.5 text-teal-600" />
            <span>Fetch Ring Events</span>
          </button>
        </div>
      </div>

      {/* Events Table */}
      <RecentEvents
        events={filteredEvents}
        isLoading={isLoading}
        onSelectEvent={onSelectEvent}
        onQuickAcknowledge={onQuickAcknowledge}
        onQuickDismiss={onQuickDismiss}
        activeStatusFilter={statusFilter}
        onChangeStatusFilter={setStatusFilter}
      />
    </div>
  );
};
