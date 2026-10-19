import React, { useState } from 'react';
import { HourlyActivityBucket } from '../../types/events';
import { Activity, Clock } from 'lucide-react';

interface ActivityChartProps {
  data: HourlyActivityBucket[];
  isLoading?: boolean;
}

export const ActivityChart: React.FC<ActivityChartProps> = ({ data, isLoading }) => {
  const [activeBucket, setActiveBucket] = useState<HourlyActivityBucket | null>(null);

  const maxEvents = Math.max(...data.map(d => d.totalEvents), 4);

  return (
    <div className="rounded-xl bg-white border border-slate-200/80 shadow-sm p-5 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700">
              <Activity className="w-4 h-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900">
              Caregiver Activity Timeline Today
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Hourly distribution of motion sensor events & AI review triggers
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-teal-600" />
            <span className="text-slate-600">Normal</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-500" />
            <span className="text-amber-800 font-medium">Requires Review</span>
          </div>
        </div>
      </div>

      {/* Bar Chart Visualization */}
      <div className="relative pt-4 pb-2">
        {activeBucket && (
          <div className="absolute top-0 right-4 px-2.5 py-1 rounded bg-slate-900 text-white text-xs font-mono shadow-lg pointer-events-none flex items-center gap-2 animate-in fade-in duration-150">
            <Clock className="w-3 h-3 text-teal-400" />
            <span>
              {activeBucket.hourLabel}: {activeBucket.totalEvents} events (
              {activeBucket.reviewEvents > 0 ? (
                <span className="text-amber-300 font-semibold">
                  {activeBucket.reviewEvents} review
                </span>
              ) : (
                <span className="text-slate-300">0 review</span>
              )}
              )
            </span>
          </div>
        )}

        <div className="grid grid-cols-9 gap-2 sm:gap-4 items-end h-28 border-b border-slate-200 pb-2">
          {data.map((bucket, idx) => {
            const heightPercent = Math.max(12, (bucket.totalEvents / maxEvents) * 100);
            const reviewHeightPercent =
              bucket.totalEvents > 0
                ? (bucket.reviewEvents / bucket.totalEvents) * heightPercent
                : 0;
            const normalHeightPercent = heightPercent - reviewHeightPercent;

            return (
              <div
                key={idx}
                onMouseEnter={() => setActiveBucket(bucket)}
                onMouseLeave={() => setActiveBucket(null)}
                className="group flex flex-col items-center justify-end h-full cursor-pointer relative"
              >
                {/* Bar */}
                <div className="w-full max-w-[28px] rounded-t overflow-hidden flex flex-col justify-end transition-all group-hover:scale-105 duration-150">
                  {/* Review portion (Amber) */}
                  {reviewHeightPercent > 0 && (
                    <div
                      style={{ height: `${reviewHeightPercent}%` }}
                      className="w-full bg-amber-500 transition-all group-hover:bg-amber-600"
                    />
                  )}
                  {/* Normal portion (Teal) */}
                  <div
                    style={{ height: `${normalHeightPercent}%` }}
                    className="w-full bg-teal-600/80 transition-all group-hover:bg-teal-600"
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Hour Axis Labels */}
        <div className="grid grid-cols-9 gap-2 sm:gap-4 text-center mt-2">
          {data.map((bucket, idx) => (
            <span
              key={idx}
              className={`text-[11px] font-mono tabular-nums ${
                bucket.hourLabel === 'Now'
                  ? 'text-teal-700 font-semibold'
                  : 'text-slate-500'
              }`}
            >
              {bucket.hourLabel}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
