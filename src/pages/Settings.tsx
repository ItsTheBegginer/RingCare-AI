import React, { useState } from 'react';
import { CaregiverSettings, Camera } from '../types/events';
import { EmptyState, LoadingSkeleton, ErrorState } from '../components/common/FeedbackStates';
import {
  Settings2,
  Video,
  User,
  Bell,
  Shield,
  RefreshCw,
} from 'lucide-react';

interface SettingsPageProps {
  settings: CaregiverSettings | null;
  cameras: Camera[];
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onUpdateSettings: (partial: Partial<CaregiverSettings>) => Promise<void>;
  onToggleCamera: (cameraId: string) => void;
  onResetDemoData: () => Promise<void>;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({
  settings,
  cameras,
  isLoading,
  error,
  onRetry,
  onUpdateSettings,
  onToggleCamera,
  onResetDemoData,
}) => {
  const [localSettings, setLocalSettings] = useState<CaregiverSettings | null>(
    settings ? { ...settings } : null
  );

  // Sync state if settings prop changes from backend
  React.useEffect(() => {
    if (settings) {
      setLocalSettings({ ...settings });
    }
  }, [settings]);

  const handleToggle = async (key: keyof CaregiverSettings, value: boolean) => {
    if (!localSettings) return;
    const updated = { ...localSettings, [key]: value };
    setLocalSettings(updated);
    await onUpdateSettings({ [key]: value });
  };

  if (error) {
    return (
      <div className="space-y-6 max-w-4xl">
        <ErrorState
          title="Settings Error"
          description={error}
          actionText="Retry"
          onAction={onRetry}
        />
      </div>
    );
  }

  if (isLoading || !localSettings) {
    return (
      <div className="space-y-6 max-w-4xl p-6 bg-white rounded-xl border border-slate-200/80">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Top Banner */}
      <div className="p-4 sm:p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700 shadow-2xs">
            <Settings2 className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Monitoring Configuration</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Alert preferences, connected cameras, and location profile
            </p>
          </div>
        </div>
        <span className="text-[11px] font-mono text-teal-800 bg-teal-50 border border-teal-200/80 px-2.5 py-0.5 rounded-md font-medium">
          Backend Sync
        </span>
      </div>

      {/* Section 1: Monitoring Toggles */}
      <div className="rounded-xl bg-white border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center gap-2 bg-slate-50/60">
          <Bell className="w-4 h-4 text-teal-600" />
          <h3 className="text-sm font-bold text-slate-900">Monitoring Controls</h3>
        </div>

        <div className="p-5 space-y-3 bg-white">
          {/* Monitoring Enabled */}
          <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
            <div>
              <span className="text-xs font-semibold text-slate-900 block">
                Continuous Security Monitoring
              </span>
              <span className="text-[11px] text-slate-500">
                Master switch for real-time motion detection and event processing.
              </span>
            </div>
            <button
              onClick={() => handleToggle('monitoringEnabled', !localSettings.monitoringEnabled)}
              className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                localSettings.monitoringEnabled ? 'bg-teal-600' : 'bg-slate-300'
              }`}
            >
              <div
                className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
                  localSettings.monitoringEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Review Notifications */}
          <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
            <div>
              <span className="text-xs font-semibold text-slate-900 block">
                High-Severity Alert Notifications
              </span>
              <span className="text-[11px] text-slate-500">
                Send SNS email alerts when a medium or high priority event is detected.
              </span>
            </div>
            <button
              onClick={() =>
                handleToggle(
                  'reviewNotificationsEnabled',
                  !localSettings.reviewNotificationsEnabled
                )
              }
              className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                localSettings.reviewNotificationsEnabled ? 'bg-teal-600' : 'bg-slate-300'
              }`}
            >
              <div
                className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
                  localSettings.reviewNotificationsEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Security Detection */}
          <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
            <div>
              <span className="text-xs font-semibold text-slate-900 block">
                Security Detection
              </span>
              <span className="text-[11px] text-slate-500">
                Detect possible weapons and face coverings in Ring footage using Amazon Rekognition labels.
              </span>
            </div>
            <button
              onClick={() =>
                handleToggle('securityDetectionEnabled', !localSettings.securityDetectionEnabled)
              }
              className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                localSettings.securityDetectionEnabled ? 'bg-teal-600' : 'bg-slate-300'
              }`}
            >
              <div
                className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
                  localSettings.securityDetectionEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Section 2: Camera Hardware Management */}
      <div className="rounded-xl bg-white border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center gap-2 bg-slate-50/60">
          <Video className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-bold text-slate-900">Camera Sensors</h3>
        </div>

        <div className="p-5 bg-white">
          <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-lg overflow-hidden bg-white text-xs">
            {cameras.map(camera => (
              <div key={camera.id} className="p-3.5 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{camera.name}</span>
                    <span className="text-[10px] font-mono text-slate-400">({camera.id})</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {camera.location} · {camera.resolution}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`px-2 py-0.5 text-[10px] font-mono rounded ${
                      camera.status === 'online'
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : 'bg-rose-50 text-rose-700 border border-rose-200'
                    }`}
                  >
                    {camera.status === 'online' ? 'Online' : 'Offline'}
                  </span>

                  <button
                    onClick={() => onToggleCamera(camera.id)}
                    className="px-2.5 py-1 text-xs text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/80 border border-slate-200/80 rounded-md transition-colors font-medium"
                  >
                    Toggle
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Section 3: Location Profile */}
      <div className="rounded-xl bg-white border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center gap-2 bg-slate-50/60">
          <User className="w-4 h-4 text-teal-600" />
          <h3 className="text-sm font-bold text-slate-900">Monitored Location Profile</h3>
        </div>

        <div className="p-5 bg-white">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-slate-500 text-[11px] block">Location Name</span>
              <span className="font-bold text-slate-900 mt-0.5 block">
                {localSettings.residentProfile.name}
              </span>
            </div>

            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-slate-500 text-[11px] block">Address / Site</span>
              <span className="font-bold text-slate-900 mt-0.5 block">
                {localSettings.residentProfile.residence}
              </span>
            </div>

            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-slate-500 text-[11px] block">Alert Contact</span>
              <span className="font-bold text-slate-900 mt-0.5 block">
                {localSettings.residentProfile.emergencyContact} ({localSettings.residentProfile.emergencyPhone})
              </span>
            </div>

            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-slate-500 text-[11px] block">Notes</span>
              <span className="text-slate-700 mt-0.5 block leading-normal font-normal">
                {localSettings.residentProfile.notes}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Section 4: Reset Button */}
      <div className="p-4 sm:p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm flex items-center justify-between">
        <div>
          <span className="text-xs font-bold text-slate-900 block">Reset Event Data</span>
          <span className="text-[11px] text-slate-500">
            Clear all stored events and reset the dashboard to a clean state.
          </span>
        </div>
        <button
          onClick={onResetDemoData}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg transition-colors shadow-2xs"
        >
          <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
          <span>Reset Events</span>
        </button>
      </div>
    </div>
  );
};
