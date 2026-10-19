import React from 'react';
import { Camera } from '../types/events';
import { CameraCard } from '../components/cameras/CameraCard';
import { EmptyState, ErrorState } from '../components/common/FeedbackStates';
import { Video, ShieldCheck, Info } from 'lucide-react';

interface CamerasPageProps {
  cameras: Camera[];
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
  onSelectCamera: (cameraId: string) => void;
  onToggleStatus: (cameraId: string) => void;
}

export const CamerasPage: React.FC<CamerasPageProps> = ({
  cameras,
  isLoading,
  error,
  onRetry,
  onSelectCamera,
  onToggleStatus,
}) => {
  return (
    <div className="space-y-6">
      {error && (
        <ErrorState
          title="Camera Stream Connection Issue"
          description={error}
          actionText="Retry Cameras"
          onAction={onRetry}
        />
      )}

      {/* Top Banner Notice */}
      <div className="p-4 sm:p-5 rounded-xl bg-white border border-slate-200/80 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700 shrink-0">
            <Video className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Connected Monitoring Cameras ({cameras.length})
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              High-definition sensor viewpoints configured for motion boundary detection
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-teal-800 bg-teal-50 border border-teal-200/80 px-3 py-1.5 rounded-lg font-medium">
            <Info className="w-3.5 h-3.5 text-teal-600" />
            <span>Prototype: WebRTC / WHEP stream mock</span>
          </div>
        </div>
      </div>

      {/* Camera Grid or States */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-5">
          {[1, 2, 3, 4].map(i => (
            <div
              key={i}
              className="h-64 rounded-xl bg-slate-100/90 border border-slate-200/80 animate-pulse p-5 flex flex-col justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-200" />
                <div className="space-y-1.5 flex-1">
                  <div className="w-36 h-4 bg-slate-200 rounded" />
                  <div className="w-24 h-3 bg-slate-200/70 rounded" />
                </div>
              </div>
              <div className="h-28 bg-slate-200/60 rounded-lg" />
              <div className="h-8 bg-slate-200/70 rounded-lg" />
            </div>
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <EmptyState
          title="No cameras registered"
          description="No camera sensors have been registered yet. Add a Ring device token or simulate sample clips."
          actionText="Retry Cameras"
          onAction={onRetry}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-5">
          {cameras.map(camera => (
            <CameraCard
              key={camera.id}
              camera={camera}
              onSelectCamera={onSelectCamera}
              onToggleStatus={onToggleStatus}
            />
          ))}
        </div>
      )}

      {/* Integration Notice Card */}
      <div className="p-4 rounded-xl bg-teal-50/60 border border-teal-200/80 text-xs text-slate-700 leading-relaxed flex items-start gap-3 shadow-xs">
        <ShieldCheck className="w-4 h-4 text-teal-700 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-slate-900 block mb-0.5">
            Ring Video Stream Integration Readiness
          </span>
          In production, these cards will render authenticated low-latency WebRTC streams
          directly from the Ring video proxy. All motion boundary and optical flow calculations
          are transmitted as lightweight telemetry to save bandwidth and preserve resident privacy.
        </div>
      </div>
    </div>
  );
};
