import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ArrowLeftRight,
  AlertOctagon,
  FileSearch,
  Database,
} from 'lucide-react';

interface SidebarProps {
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (open: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  mobileMenuOpen,
  setMobileMenuOpen,
}) => {
  const navItems = [
    {
      to: '/',
      label: 'Dashboard',
      icon: <LayoutDashboard className="w-4 h-4" />,
      end: true,
    },
    {
      to: '/transactions',
      label: 'Transactions',
      icon: <ArrowLeftRight className="w-4 h-4" />,
    },
    {
      to: '/alerts',
      label: 'Alerts',
      icon: <AlertOctagon className="w-4 h-4" />,
    },
    {
      to: '/investigations',
      label: 'Investigations',
      icon: <FileSearch className="w-4 h-4" />,
    },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/80 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed lg:sticky top-16 z-40 h-[calc(100vh-4rem)] w-64 bg-slate-900 border-r border-slate-800/80 flex flex-col justify-between transition-transform duration-200 ease-in-out ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="p-4 space-y-6">
          <div>
            <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Navigation
            </p>
            <nav className="space-y-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={() => setMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                    }`
                  }
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          <div>
            <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
              System Sources
            </p>
            <div className="px-3 py-2.5 rounded-lg bg-slate-950/60 border border-slate-800/70 text-xs space-y-2">
              <div className="flex items-center justify-between text-slate-400">
                <span className="flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-emerald-400" />
                  PostgreSQL
                </span>
                <span className="text-[10px] text-emerald-400 font-mono">Connected</span>
              </div>
              <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800/80">
                Data pipeline: FastAPI + MLflow + XGBoost
              </div>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="p-4 border-t border-slate-800/80 text-xs text-slate-400 space-y-1">
          <p className="font-medium text-slate-300">BankGuard v0.1.0</p>
          <p className="text-[11px]">Real-Time Fraud & AML Shield</p>
        </div>
      </aside>
    </>
  );
};
