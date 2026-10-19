import React from 'react';
import { Calendar, AlertTriangle, CheckCircle2, Video } from 'lucide-react';
import { DashboardSummary } from '../../types/events';

interface SummaryCardsProps {
  summary: DashboardSummary | null;
  isLoading: boolean;
  onFilterReviewClick?: () => void;
  onFilterNormalClick?: () => void;
  onFilterAllClick?: () => void;
  onCamerasClick?: () => void;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({
  summary,
  isLoading,
  onFilterReviewClick,
  onFilterNormalClick,
  onFilterAllClick,
  onCamerasClick,
}) => {
  const cards = [
    {
      title: "Today's Events",
      value: summary?.todayEventsCount ?? 0,
      label: "Total telemetry events logged",
      icon: Calendar,
      accent: 'border-slate-200/80 bg-white hover:border-indigo-300 shadow-[0_2px_8px_-2px_rgba(15,23,42,0.05)]',
      titleColor: 'text-slate-600 font-medium',
      valueColor: 'text-slate-900 font-mono',
      labelColor: 'text-slate-500',
      iconBg: 'bg-indigo-50 text-indigo-600 border border-indigo-200/60',
      badge: '24h cycle',
      badgeColor: 'text-indigo-700 bg-indigo-50/80 border border-indigo-200/60',
      onClick: onFilterAllClick,
    },
    {
      title: 'Requires Review',
      value: summary?.requiresReviewCount ?? 0,
      label: 'Events requiring attention',
      icon: AlertTriangle,
      accent:
        (summary?.requiresReviewCount ?? 0) > 0
          ? 'border-amber-200/90 bg-gradient-to-b from-amber-50/50 via-amber-50/15 to-white hover:border-amber-300 shadow-[0_2px_8px_-2px_rgba(245,158,11,0.12)]'
          : 'border-slate-200/80 bg-white hover:border-slate-300 shadow-[0_2px_8px_-2px_rgba(15,23,42,0.05)]',
      titleColor: (summary?.requiresReviewCount ?? 0) > 0 ? 'text-amber-900 font-medium' : 'text-slate-600 font-medium',
      valueColor: (summary?.requiresReviewCount ?? 0) > 0 ? 'text-amber-950 font-mono' : 'text-slate-900 font-mono',
      labelColor: (summary?.requiresReviewCount ?? 0) > 0 ? 'text-amber-700/90' : 'text-slate-500',
      iconBg:
        (summary?.requiresReviewCount ?? 0) > 0
          ? 'bg-amber-100 text-amber-700 border border-amber-200'
          : 'bg-slate-100 text-slate-500',
      badge: (summary?.requiresReviewCount ?? 0) > 0 ? 'Action needed' : 'Clear',
      badgeColor:
        (summary?.requiresReviewCount ?? 0) > 0
          ? 'text-amber-800 bg-amber-100/80 border border-amber-200'
          : 'text-slate-600 bg-slate-100',
      onClick: onFilterReviewClick,
    },
    {
      title: 'Normal Activity',
      value: summary?.normalActivityCount ?? 0,
      label: 'Verified routine movement',
      icon: CheckCircle2,
      accent: 'border-slate-200/80 bg-white hover:border-emerald-300 shadow-[0_2px_8px_-2px_rgba(15,23,42,0.05)]',
      titleColor: 'text-slate-600 font-medium',
      valueColor: 'text-slate-900 font-mono',
      labelColor: 'text-slate-500',
      iconBg: 'bg-emerald-50 text-emerald-600 border border-emerald-200/60',
      badge: 'Normal flow',
      badgeColor: 'text-emerald-700 bg-emerald-50 border border-emerald-200/60',
      onClick: onFilterNormalClick,
    },
    {
      title: 'Cameras Online',
      value: `${summary?.camerasOnlineCount ?? 0}/${summary?.totalCamerasCount ?? 0}`,
      label: 'All sensors responding',
      icon: Video,
      accent: 'border-slate-200/80 bg-white hover:border-teal-300 shadow-[0_2px_8px_-2px_rgba(15,23,42,0.05)]',
      titleColor: 'text-slate-600 font-medium',
      valueColor: 'text-slate-900 font-mono',
      labelColor: 'text-slate-500',
      iconBg: 'bg-teal-50 text-teal-600 border border-teal-200/60',
      badge: '100% active',
      badgeColor: 'text-teal-700 bg-teal-50 border border-teal-200/60',
      onClick: onCamerasClick,
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            onClick={card.onClick}
            role={card.onClick ? 'button' : undefined}
            tabIndex={card.onClick ? 0 : undefined}
            onKeyDown={e => {
              if (card.onClick && (e.key === 'Enter' || e.key === ' ')) {
                card.onClick();
              }
            }}
            className={`p-4 sm:p-4.5 rounded-xl border transition-all duration-200 text-left ${
              card.accent
            } ${
              card.onClick
                ? 'cursor-pointer hover:shadow-md active:scale-[0.99] focus:outline-none focus:ring-2 focus:ring-teal-500'
                : ''
            }`}
          >
            <div className="flex items-start justify-between">
              <span className={`text-xs ${card.titleColor}`}>
                {card.title}
              </span>
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center ${card.iconBg}`}
              >
                <Icon className="w-4 h-4 shrink-0" />
              </div>
            </div>

            <div className="mt-2.5 flex items-baseline gap-2">
              <span className={`text-2xl sm:text-3xl font-bold tracking-tight tabular-nums ${card.valueColor}`}>
                {isLoading ? '—' : card.value}
              </span>
              {card.badge && (
                <span
                  className={`text-[10px] font-medium font-mono px-1.5 py-0.5 rounded ${
                    card.badgeColor
                  }`}
                >
                  {card.badge}
                </span>
              )}
            </div>

            <p className={`mt-1 text-xs leading-snug ${card.labelColor}`}>{card.label}</p>
          </div>
        );
      })}
    </div>
  );
};
