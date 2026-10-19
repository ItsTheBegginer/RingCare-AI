/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Event,
  Camera,
  DashboardSummary,
  HourlyActivityBucket,
  CaregiverSettings,
  EventStatus,
} from './types/events';
import { ringCareApi } from './services/api';
import { Sidebar, NavigationTab } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { ArchitectureModal } from './components/layout/ArchitectureModal';
import { EventDetailsModal } from './components/events/EventDetailsModal';
import { ToastProvider, useToast } from './components/common/Toast';
import { DashboardPage } from './pages/Dashboard';
import { LiveEventsPage } from './pages/LiveEvents';
import { CamerasPage } from './pages/Cameras';
import { ActivityPage } from './pages/Activity';
import { SettingsPage } from './pages/Settings';

const isActionedStatus = (status: EventStatus) =>
  status === 'acknowledged' || status === 'dismissed';

export const mergeEvents = (prev: Event[], incoming: Event[]): Event[] => {
  const byId = new Map(prev.map(e => [e.id, e]));

  for (const inc of incoming) {
    const existing = byId.get(inc.id);
    if (!existing) {
      byId.set(inc.id, inc);
    } else {
      // Never revert an acknowledged or dismissed status back to review/normal
      const shouldKeepExistingStatus =
        isActionedStatus(existing.aiStatus) && !isActionedStatus(inc.aiStatus);

      byId.set(inc.id, {
        ...existing,
        ...inc,
        aiStatus: shouldKeepExistingStatus ? existing.aiStatus : inc.aiStatus,
        actionLog: shouldKeepExistingStatus
          ? (existing.actionLog || inc.actionLog)
          : (inc.actionLog || existing.actionLog),
        thumbnail: inc.thumbnail || existing.thumbnail || null,
        clipUrl: inc.clipUrl || existing.clipUrl || null,
      });
    }
  }

  return [...byId.values()].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
};

const MainAppContent: React.FC = () => {
  const { showToast } = useToast();

  const [currentTab, setCurrentTab] = useState<NavigationTab>('dashboard');
  const [events, setEvents] = useState<Event[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [hourlyActivity, setHourlyActivity] = useState<HourlyActivityBucket[]>([]);
  const [settings, setSettings] = useState<CaregiverSettings | null>(null);

  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [isEventModalOpen, setIsEventModalOpen] = useState(false);
  const [isArchitectureModalOpen, setIsArchitectureModalOpen] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  const [activeStatusFilter, setActiveStatusFilter] = useState<'all' | EventStatus>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  // Initial Data Fetch
  const refreshData = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [eventsData, camerasData, summaryData, hourlyData, settingsData] =
        await Promise.all([
          ringCareApi.getEvents(),
          ringCareApi.getCameras(),
          ringCareApi.getDashboardSummary(),
          ringCareApi.getHourlyActivity(),
          ringCareApi.getSettings(),
        ]);

      setEvents(prev => (prev.length === 0 ? eventsData : mergeEvents(prev, eventsData)));
      setCameras(camerasData);
      setSummary(summaryData);
      setHourlyActivity(hourlyData);
      setSettings(settingsData);
    } catch (err: any) {
      const msg = err?.message || 'Could not fetch care monitor state.';
      setLoadError(msg);
      showToast('error', 'Failed to load telemetry', msg);
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // Live updates pushed by the backend (new Ring events / webhook / polling)
  useEffect(() => {
    return ringCareApi.subscribeToEvents(ev => {
      setEvents(prev => mergeEvents(prev, [ev]));
      setSelectedEvent(cur => {
        if (cur && cur.id === ev.id) {
          const shouldKeepStatus = isActionedStatus(cur.aiStatus) && !isActionedStatus(ev.aiStatus);
          return {
            ...cur,
            ...ev,
            aiStatus: shouldKeepStatus ? cur.aiStatus : ev.aiStatus,
            actionLog: shouldKeepStatus ? cur.actionLog : (ev.actionLog || cur.actionLog),
            thumbnail: ev.thumbnail || cur.thumbnail,
            clipUrl: ev.clipUrl || cur.clipUrl,
          };
        }
        return cur;
      });
      Promise.all([
        ringCareApi.getDashboardSummary(),
        ringCareApi.getCameras(),
        ringCareApi.getHourlyActivity(),
      ])
        .then(([s, c, h]) => {
          setSummary(s);
          setCameras(c);
          setHourlyActivity(h);
        })
        .catch(() => {});
    });
  }, []);

  // Acknowledge Event Action
  const handleAcknowledgeEvent = async (id: string, note?: string) => {
    try {
      const updated = await ringCareApi.acknowledgeEvent(id, note);
      setEvents(prev => prev.map(e => (e.id === id ? updated : e)));
      if (selectedEvent?.id === id) {
        setSelectedEvent(cur => (cur ? { ...cur, ...updated, thumbnail: cur.thumbnail } : updated));
      }
      // Refresh summary numbers
      const newSummary = await ringCareApi.getDashboardSummary();
      setSummary(newSummary);
      showToast(
        'success',
        `Event ${id} Acknowledged`,
        `Marked by primary caregiver: ${updated.cameraName}`
      );
    } catch (err) {
      showToast('error', 'Action failed', 'Unable to acknowledge event.');
    }
  };

  // Dismiss Event Action
  const handleDismissEvent = async (id: string, note?: string) => {
    try {
      const updated = await ringCareApi.dismissEvent(id, note);
      setEvents(prev => prev.map(e => (e.id === id ? updated : e)));
      if (selectedEvent?.id === id) {
        setSelectedEvent(cur => (cur ? { ...cur, ...updated, thumbnail: cur.thumbnail } : updated));
      }
      // Refresh summary numbers
      const newSummary = await ringCareApi.getDashboardSummary();
      setSummary(newSummary);
      showToast(
        'info',
        `Event ${id} Dismissed`,
        `Logged as non-critical: ${updated.cameraName}`
      );
    } catch (err) {
      showToast('error', 'Action failed', 'Unable to dismiss event.');
    }
  };

  // Pull new events + clips from Ring (or a local sample clip if Ring isn't configured)
  const handleSimulateEvent = async () => {
    setIsSimulating(true);
    try {
      const { events: fresh, source, notes } = await ringCareApi.fetchNewEvents();
      if (fresh.length > 0) {
        setEvents(prev => mergeEvents(prev, fresh));
        const [newSummary, newCameras, newHourly] = await Promise.all([
          ringCareApi.getDashboardSummary(),
          ringCareApi.getCameras(),
          ringCareApi.getHourlyActivity(),
        ]);
        setSummary(newSummary);
        setCameras(newCameras);
        setHourlyActivity(newHourly);
        showToast(
          'warning',
          source === 'ring' ? `${fresh.length} new Ring event(s) analysed` : 'Sample clip analysed',
          `${fresh[0].cameraName}: ${fresh[0].summary}`
        );
      } else {
        showToast('info', 'No new Ring events', notes[0] ?? 'Trigger a live-view/motion event in the Ring Playground, then try again.');
      }
    } catch (err) {
      showToast('error', 'Fetch failed', err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsSimulating(false);
    }
  };

  // Reset demo state
  const handleResetData = async () => {
    setIsLoading(true);
    try {
      await ringCareApi.resetDemoData();
      await refreshData();
      showToast('info', 'Demo Data Reset', 'Restored pristine demonstration events and sensors.');
    } finally {
      setIsLoading(false);
    }
  };

  // Toggle Camera Online/Offline
  const handleToggleCamera = async (cameraId: string) => {
    try {
      const updatedCamera = await ringCareApi.toggleCameraState(cameraId);
      setCameras(prev => prev.map(c => (c.id === cameraId ? updatedCamera : c)));
      const newSummary = await ringCareApi.getDashboardSummary();
      setSummary(newSummary);
      showToast(
        'info',
        `${updatedCamera.name} is now ${updatedCamera.status}`,
        `Camera view preference saved in this browser.`
      );
    } catch {
      showToast('error', 'Failed to toggle camera state');
    }
  };

  // Update Settings
  const handleUpdateSettings = async (partial: Partial<CaregiverSettings>) => {
    try {
      const updated = await ringCareApi.updateSettings(partial);
      setSettings(updated);
      const newSummary = await ringCareApi.getDashboardSummary();
      setSummary(newSummary);
      showToast('success', 'Settings Saved', 'Caregiver monitoring preferences updated.');
    } catch {
      showToast('error', 'Failed to update settings');
    }
  };

  // Open Event Modal
  const handleOpenEvent = (event: Event) => {
    setSelectedEvent(event);
    setIsEventModalOpen(true);
    ringCareApi
      .getEvent(event.id)
      .then(full => {
        if (full) setSelectedEvent(cur => (cur && cur.id === full.id ? full : cur));
      })
      .catch(() => {});
  };

  // Select camera from camera card -> route to Live Events filtered by camera
  const handleSelectCameraEvents = (cameraId: string) => {
    setCurrentTab('live-events');
  };

  return (
    <div className="min-h-screen bg-[#f3f5f8] text-slate-900 flex flex-col lg:flex-row antialiased">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        reviewCount={summary?.requiresReviewCount ?? 0}
        camerasOnlineCount={summary?.camerasOnlineCount ?? 0}
        isMobileOpen={isMobileNavOpen}
        onCloseMobile={() => setIsMobileNavOpen(false)}
        onOpenArchitectureModal={() => setIsArchitectureModalOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 lg:pl-64 flex flex-col min-w-0">
        {/* Top Header */}
        <Header
          currentTab={currentTab}
          onOpenMobileMenu={() => setIsMobileNavOpen(true)}
          onSimulateEvent={handleSimulateEvent}
          onResetData={handleResetData}
          isSimulating={isSimulating}
          monitoringActive={settings?.monitoringEnabled ?? true}
        />

        {/* Viewport Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {currentTab === 'dashboard' && (
            <DashboardPage
              summary={summary}
              events={events}
              hourlyActivity={hourlyActivity}
              isLoading={isLoading}
              error={loadError}
              onRetry={refreshData}
              onSelectEvent={handleOpenEvent}
              onQuickAcknowledge={handleAcknowledgeEvent}
              onQuickDismiss={handleDismissEvent}
              activeStatusFilter={activeStatusFilter}
              onChangeStatusFilter={setActiveStatusFilter}
              onNavigateTab={setCurrentTab}
            />
          )}

          {currentTab === 'live-events' && (
            <LiveEventsPage
              events={events}
              cameras={cameras}
              isLoading={isLoading}
              error={loadError}
              onRetry={refreshData}
              onSelectEvent={handleOpenEvent}
              onQuickAcknowledge={handleAcknowledgeEvent}
              onQuickDismiss={handleDismissEvent}
              onSimulateEvent={handleSimulateEvent}
              isSimulating={isSimulating}
            />
          )}

          {currentTab === 'cameras' && (
            <CamerasPage
              cameras={cameras}
              isLoading={isLoading}
              error={loadError}
              onRetry={refreshData}
              onSelectCamera={handleSelectCameraEvents}
              onToggleStatus={handleToggleCamera}
            />
          )}

          {currentTab === 'activity' && (
            <ActivityPage
              events={events}
              cameras={cameras}
              isLoading={isLoading}
              error={loadError}
              onRetry={refreshData}
              onSelectEvent={handleOpenEvent}
              onQuickAcknowledge={handleAcknowledgeEvent}
              onQuickDismiss={handleDismissEvent}
            />
          )}

          {currentTab === 'settings' && (
            <SettingsPage
              settings={settings}
              cameras={cameras}
              isLoading={isLoading}
              error={loadError}
              onRetry={refreshData}
              onUpdateSettings={handleUpdateSettings}
              onToggleCamera={handleToggleCamera}
              onResetDemoData={handleResetData}
            />
          )}
        </main>
      </div>

      {/* Event Details Drawer / Modal */}
      <EventDetailsModal
        event={selectedEvent}
        isOpen={isEventModalOpen}
        onClose={() => {
          setIsEventModalOpen(false);
          setSelectedEvent(null);
        }}
        onAcknowledge={handleAcknowledgeEvent}
        onDismiss={handleDismissEvent}
      />

      {/* Future Architecture & API Contract Modal */}
      <ArchitectureModal
        isOpen={isArchitectureModalOpen}
        onClose={() => setIsArchitectureModalOpen(false)}
      />
    </div>
  );
};

export default function App() {
  return (
    <ToastProvider>
      <MainAppContent />
    </ToastProvider>
  );
}
