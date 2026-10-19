import React from 'react';
import { Menu, Zap, RefreshCw, UserCheck } from 'lucide-react';
import { NavigationTab } from './Sidebar';

interface HeaderProps {
  currentTab: NavigationTab;
  onOpenMobileMenu: () => void;
  onSimulateEvent: () => void;
  onResetData: () => void;
  isSimulating?: boolean;
  monitoringActive?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  onOpenMobileMenu,
  onSimulateEvent,
  onResetData,
  isSimulating,
  monitoringActive = true,
}) => {
  const getTabMeta = () => {
    switch (currentTab) {
      case 'dashboard':
        return {
          title: 'Dashboard',
          description: 'Monitor activity and review events requiring attention.',
        };
      case 'live-events':
        return {
          title: 'Live Events',
          description: 'Stream of computer vision triage events with AI assessment.',
        };
      case 'cameras':
        return {
          title: 'Cameras',
          description: 'Monitor connected camera health, locations, and motion zones.',
        };
      case 'activity':
        return {
          title: 'Activity Timeline',
          description: 'Historical sequence of daily caregiver events and notes.',
        };
      case 'settings':
        return {
          title: 'Settings',
          description: 'Caregiver review preferences, monitoring parameters, and profile.',
        };
    }
  };

  const meta = getTabMeta();

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200/80 px-4 sm:px-6 py-3.5 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
      <div className="flex items-center justify-between gap-4">
        {/* Left: Mobile Toggle + Page Title */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenMobileMenu}
            className="lg:hidden p-2 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight leading-tight">
              {meta.title}
            </h1>
            <p className="text-xs text-slate-500 leading-normal hidden sm:block">
              {meta.description}
            </p>
          </div>
        </div>

        {/* Right: Monitoring Status + Simulation Action + Caregiver Profile */}
        <div className="flex items-center gap-2.5 sm:gap-3.5">
          {/* Status Indicator */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-xs">
            <span
              className={`h-2 w-2 rounded-full ${
                monitoringActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
              }`}
            />
            <span className="text-emerald-800 font-medium">
              {monitoringActive ? 'Monitoring active' : 'Monitoring paused'}
            </span>
          </div>

          {/* Quick Simulation Button for Demo Testing */}
          <button
            onClick={onSimulateEvent}
            disabled={isSimulating}
            title="Pull new events and clips from Ring and run AI triage"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-teal-800 bg-teal-50 hover:bg-teal-100 border border-teal-200/90 rounded-lg transition-colors whitespace-nowrap active:scale-95 disabled:opacity-50 shadow-2xs"
          >
            <Zap className={`w-3.5 h-3.5 ${isSimulating ? 'animate-spin text-teal-600' : 'text-teal-600'}`} />
            <span className="hidden sm:inline">Fetch Ring Events</span>
            <span className="sm:hidden">Fetch</span>
          </button>

          {/* Reset Demo Data Button */}
          <button
            onClick={onResetData}
            title="Reset demonstration data"
            className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors"
            aria-label="Reset demo state"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          {/* Caregiver Profile Lockup */}
          <div className="flex items-center gap-2.5 pl-2 sm:pl-3 border-l border-slate-200">
            <div className="w-8 h-8 rounded-full bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-700 font-semibold text-xs shrink-0 shadow-2xs">
              <UserCheck className="w-4 h-4 text-teal-600" />
            </div>
            <div className="hidden xl:block text-left">
              <div className="text-xs font-semibold text-slate-900 leading-tight">
                Sarah Jenkins, RN
              </div>
              <div className="text-[10px] text-slate-500 font-mono">
                Eleanor Vance · Rm 4B
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
