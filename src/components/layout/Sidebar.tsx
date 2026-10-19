import React from 'react';
import {
  LayoutDashboard,
  Radio,
  Video,
  Clock3,
  Settings2,
  Shield,
  Layers,
  CheckCircle2,
  X,
} from 'lucide-react';

export type NavigationTab = 'dashboard' | 'live-events' | 'cameras' | 'activity' | 'settings';

interface SidebarProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  reviewCount: number;
  camerasOnlineCount: number;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
  onOpenArchitectureModal: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  reviewCount,
  camerasOnlineCount,
  isMobileOpen,
  onCloseMobile,
  onOpenArchitectureModal,
}) => {
  const navItems: Array<{
    id: NavigationTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: number;
    sublabel?: string;
  }> = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
    },
    {
      id: 'live-events',
      label: 'Live Events',
      icon: Radio,
      badge: reviewCount > 0 ? reviewCount : undefined,
    },
    {
      id: 'cameras',
      label: 'Cameras',
      icon: Video,
      sublabel: `${camerasOnlineCount} Online`,
    },
    {
      id: 'activity',
      label: 'Activity',
      icon: Clock3,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings2,
    },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isMobileOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden"
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 w-64 bg-[#0c1322] border-r border-slate-800/80 flex flex-col transition-transform duration-200 lg:translate-x-0 ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-teal-400 shadow-xs">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-base tracking-tight text-white">
                  RingCare AI
                </span>
                <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 bg-teal-950/80 border border-teal-700/60 text-teal-300 rounded">
                  PROTOTYPE
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-normal">
                Intelligent caregiver monitoring
              </p>
            </div>
          </div>
          {isMobileOpen && (
            <button
              onClick={onCloseMobile}
              className="lg:hidden p-1.5 text-slate-400 hover:text-white rounded-md"
              aria-label="Close sidebar"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Navigation list */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map(item => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSelectTab(item.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-teal-500/15 text-teal-200 font-semibold border border-teal-500/30 shadow-xs'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? 'text-teal-400' : 'text-slate-400'
                    }`}
                  />
                  <span>{item.label}</span>
                </div>

                <div className="flex items-center gap-1.5">
                  {item.sublabel && (
                    <span className="text-[10px] text-slate-400 font-mono">
                      {item.sublabel}
                    </span>
                  )}
                  {item.badge !== undefined && (
                    <span className="px-1.5 py-0.5 text-[10px] font-semibold font-mono rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      {item.badge}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </nav>

        {/* Bottom system status & architecture trigger */}
        <div className="p-3 border-t border-slate-800/80 space-y-2">
          {/* Architecture info button */}
          <button
            onClick={onOpenArchitectureModal}
            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg bg-slate-900/90 hover:bg-slate-800/90 border border-slate-800 text-[11px] text-slate-200 transition-colors text-left"
          >
            <Layers className="w-3.5 h-3.5 text-teal-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="block truncate font-medium text-slate-200">
                Future Architecture
              </span>
              <span className="block text-[10px] text-slate-400 truncate">
                Ring → OpenCV → AI Agent
              </span>
            </div>
          </button>

          {/* Operational status card */}
          <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-semibold text-slate-200 flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                System Online
              </span>
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            </div>
            <p className="text-[10px] text-slate-400 leading-normal">
              All systems operational
            </p>
            <div className="mt-1.5 pt-1.5 border-t border-slate-800 flex items-center justify-between text-[10px] text-slate-400 font-mono">
              <span>FastAPI Backend</span>
              <span className="text-teal-400 font-medium">Ready</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
