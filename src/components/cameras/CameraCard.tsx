import React from 'react';
import { Camera } from '../../types/events';
import {
  Video,
  VideoOff,
  Wifi,
  Battery,
  Clock,
  Activity,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  Maximize2,
} from 'lucide-react';

interface CameraCardProps {
  camera: Camera;
  onSelectCamera: (cameraId: string) => void;
  onToggleStatus?: (cameraId: string) => void;
}

export const CameraCard: React.FC<CameraCardProps> = ({
  camera,
  onSelectCamera,
  onToggleStatus,
}) => {
  const isOnline = camera.status === 'online';

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="rounded-xl bg-white border border-slate-200/90 shadow-xs overflow-hidden flex flex-col transition-all hover:border-slate-300 hover:shadow-sm">
      {/* Camera Video Placeholder */}
      <div className="relative aspect-video bg-slate-900 border-b border-slate-800 flex flex-col justify-between p-3 overflow-hidden select-none group text-white">
        {/* Subtle grid background to look like camera sensor viewport */}
        <div
          className="absolute inset-0 opacity-15 pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(to right, #38bdf8 1px, transparent 1px), linear-gradient(to bottom, #38bdf8 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
        />

        {/* Viewport Crosshair corners */}
        <div className="absolute top-2 left-2 w-3 h-3 border-t border-l border-slate-600" />
        <div className="absolute top-2 right-2 w-3 h-3 border-t border-r border-slate-600" />
        <div className="absolute bottom-2 left-2 w-3 h-3 border-b border-l border-slate-600" />
        <div className="absolute bottom-2 right-2 w-3 h-3 border-b border-r border-slate-600" />

        {/* Top Video Header */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm border border-slate-800 text-[11px] font-mono">
            <span
              className={`w-2 h-2 rounded-full ${
                isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'
              }`}
            />
            <span className={isOnline ? 'text-emerald-400 font-medium' : 'text-rose-400'}>
              {isOnline ? 'Online' : 'Offline'}
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm border border-slate-800 text-[10px] font-mono text-slate-300">
            <span>{camera.resolution}</span>
          </div>
        </div>

        {/* Center Placeholder Notice */}
        <div className="relative z-10 text-center my-auto px-4 py-2">
          <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 text-teal-400 flex items-center justify-center mx-auto mb-2 shadow-inner">
            {isOnline ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5 text-slate-500" />}
          </div>
          <div className="text-xs font-semibold text-slate-100">
            {camera.name}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 max-w-xs mx-auto">
            Live video not embedded - view clips in Events
          </p>
          <span className="inline-block mt-1 text-[10px] font-mono text-teal-300 bg-teal-950/80 border border-teal-800/80 px-2 py-0.5 rounded">
            Ready for Ring WebRTC / WHEP Stream
          </span>
        </div>

        {/* Bottom Video Metadata */}
        <div className="relative z-10 flex items-center justify-between text-[10px] font-mono text-slate-300 bg-black/50 backdrop-blur-sm px-2 py-1 rounded border border-slate-800/80">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <Wifi className="w-3 h-3 text-teal-400" />
              {camera.signalStrength}
            </span>
            {camera.batteryPercentage && (
              <span className="flex items-center gap-1">
                <Battery className="w-3 h-3 text-emerald-400" />
                {camera.batteryPercentage}%
              </span>
            )}
          </div>
          <span>REC: 24/7 BUFFER</span>
        </div>
      </div>

      {/* Card Details Body */}
      <div className="p-4 flex-1 flex flex-col justify-between bg-white">
        <div>
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className="text-sm font-semibold text-slate-900">{camera.name}</h4>
              <p className="text-xs text-slate-500 mt-0.5">{camera.location}</p>
            </div>
            {camera.reviewEventsToday > 0 && (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded font-mono">
                <AlertTriangle className="w-3 h-3 text-amber-600" />
                {camera.reviewEventsToday} Review
              </span>
            )}
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 gap-2 my-3 text-xs">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-[11px] text-slate-500 block flex items-center gap-1">
                <Clock className="w-3 h-3 text-slate-400" />
                Last activity
              </span>
              <span className="font-mono text-slate-800 font-semibold mt-1 block tabular-nums">
                {formatTime(camera.lastActivity)}
              </span>
            </div>

            <div className="p-2.5 rounded-lg bg-teal-50/50 border border-teal-200/70">
              <span className="text-[11px] text-teal-700 block flex items-center gap-1 font-medium">
                <Activity className="w-3 h-3 text-teal-600" />
                Motion events
              </span>
              <span className="font-mono font-bold text-teal-950 mt-1 block tabular-nums">
                {camera.motionEventsToday} today
              </span>
            </div>
          </div>

          {/* Zone Tags */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {camera.zoneTags.map((tag, idx) => (
              <span
                key={idx}
                className="text-[10px] text-slate-600 font-mono bg-slate-100 px-2 py-0.5 rounded border border-slate-200/80"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Card Footer Actions */}
        <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
          {onToggleStatus && (
            <button
              onClick={() => onToggleStatus(camera.id)}
              className="text-[11px] text-slate-500 hover:text-slate-800 transition-colors"
            >
              Toggle {isOnline ? 'Offline' : 'Online'}
            </button>
          )}

          <button
            onClick={() => onSelectCamera(camera.id)}
            className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-800 hover:text-white bg-slate-100 hover:bg-slate-900 border border-slate-200/90 rounded-lg transition-colors shadow-2xs"
          >
            <span>View Events</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
