import React from 'react';
import { Event, DashboardSummary, HourlyActivityBucket, EventStatus } from '../types/events';
import { SummaryCards } from '../components/dashboard/SummaryCard';
import { ActivityChart } from '../components/dashboard/ActivityChart';
import { RecentEvents } from '../components/dashboard/RecentEvents';
import { NavigationTab } from '../components/layout/Sidebar';
import { ErrorState } from '../components/common/FeedbackStates';
import { Shield, Sparkles } from 'lucide-react';

interface DashboardPageProps {
  summary: DashboardSummary | null;
  events: Event[];
  hourlyActivity: HourlyActivityBucket[];
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
  onSelectEvent: (event: Event) => void;
  onQuickAcknowledge: (id: string) => Promise<void>;
  onQuickDismiss: (id: string) => Promise<void>;
  activeStatusFilter: 'all' | EventStatus;
  onChangeStatusFilter: (status: 'all' | EventStatus) => void;
  onNavigateTab: (tab: NavigationTab) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  summary,
  events,
  hourlyActivity,
  isLoading,
  error,
  onRetry,
  onSelectEvent,
  onQuickAcknowledge,
  onQuickDismiss,
  activeStatusFilter,
  onChangeStatusFilter,
  onNavigateTab,
}) => {
  return (
    <div className="space-y-6">
      {error && (
        <ErrorState
          title="Telemetry Connection Issue"
          description={error}
          actionText="Retry Connection"
          onAction={onRetry}
        />
      )}

      {/* Resident Context Banner */}
      <div className="p-4 sm:p-5 rounded-xl bg-white border border-slate-200/80 shadow-[0_2px_8px_-2px_rgba(15,23,42,0.05)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700 shrink-0 shadow-2xs">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-slate-900">
                Active Monitoring: Eleanor Vance
              </span>
              <span className="text-[11px] text-teal-900 font-semibold font-mono bg-teal-50 border border-teal-200/80 px-2 py-0.5 rounded-md">
                Residence Apt 4B
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Autonomous computer vision triage active on 4 connected sensors.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={() => onNavigateTab('cameras')}
            className="px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200/80 text-slate-700 border border-slate-200/80 transition-colors font-medium"
          >
            Manage Cameras
          </button>
          <button
            onClick={() => onNavigateTab('activity')}
            className="px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white shadow-xs transition-colors font-medium"
          >
            Full Timeline
          </button>
        </div>
      </div>

      {/* 4 Summary Metric Cards */}
      <SummaryCards
        summary={summary}
        isLoading={isLoading}
        onFilterReviewClick={() => {
          onChangeStatusFilter('review');
        }}
        onFilterNormalClick={() => {
          onChangeStatusFilter('normal');
        }}
        onFilterAllClick={() => {
          onChangeStatusFilter('all');
        }}
        onCamerasClick={() => onNavigateTab('cameras')}
      />

      {/* Activity Chart (Data Visualization) */}
      <ActivityChart data={hourlyActivity} isLoading={isLoading} />

      {/* Recent Triage Events Table */}
      <RecentEvents
        events={events}
        isLoading={isLoading}
        onSelectEvent={onSelectEvent}
        onQuickAcknowledge={onQuickAcknowledge}
        onQuickDismiss={onQuickDismiss}
        activeStatusFilter={activeStatusFilter}
        onChangeStatusFilter={onChangeStatusFilter}
        onViewAllClick={() => onNavigateTab('live-events')}
        maxDisplay={8}
      />
    </div>
  );
};
