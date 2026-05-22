import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import { useTheme } from '../theme';
import {
  LayoutDashboard,
  Users,
  FileCheck,
  ShieldCheck,
  LogOut,
  Scale,
  ClipboardList,
  X,
  Brain,
  Search,
  Send,
  MessageSquare,
  Sun,
  Moon,
  Menu,
  BarChart3,
  HeartPulse,
} from 'lucide-react';
import clsx from 'clsx';

const nav = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', section: 'Main' },
  { to: '/patients', icon: Users, label: 'Patients', section: 'Main' },
  { to: '/prior-auth', icon: FileCheck, label: 'Requests', section: 'Main' },
  { to: '/eligibility', icon: HeartPulse, label: 'Eligibility', section: 'Management' },
  { to: '/policies', icon: ShieldCheck, label: 'Policies', section: 'Management' },
  { to: '/appeals', icon: Scale, label: 'Appeals', section: 'Management' },
  { to: '/audit-log', icon: ClipboardList, label: 'Audit Log', section: 'System' },
];

const agents = [
  { name: 'Clinical Reader', desc: 'Extracts evidence from patient records', icon: Brain, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  { name: 'Policy Agent', desc: 'Matches criteria against payer rules', icon: Search, color: 'text-violet-400', bg: 'bg-violet-500/10' },
  { name: 'Submission Agent', desc: 'Assembles & submits PA requests', icon: Send, color: 'text-amber-400', bg: 'bg-amber-500/10' },
  { name: 'Appeal Agent', desc: 'Handles denials & drafts appeals', icon: MessageSquare, color: 'text-rose-400', bg: 'bg-rose-500/10' },
];

const sections = ['Main', 'Management', 'System'];

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggle, isDark } = useTheme();
  const navigate = useNavigate();
  const [showAgents, setShowAgents] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className={clsx('flex h-screen transition-colors duration-300', isDark ? 'bg-[#0d1117]' : 'bg-[#f0f2f5]')}>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={clsx(
        'fixed lg:static z-50 h-full w-[260px] flex flex-col shrink-0 transition-all duration-300',
        isDark ? 'bg-[#0f1419] border-r border-white/5' : 'bg-[#1a1d23] border-r border-black/5',
        mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      )}>
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-5 border-b border-white/5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <span className="text-white font-bold text-[12px] font-mono">MX</span>
          </div>
          <div>
            <span className="font-bold text-white text-[15px] tracking-tight">MEDIX</span>
            <span className="block text-[9px] text-emerald-400 font-mono tracking-wider">PRIOR AUTH AI</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto">
          {sections.map((section, si) => (
            <div key={section}>
              {si > 0 && <div className="h-px bg-white/5 my-3 mx-2" />}
              <p className="text-[9px] font-bold text-white/30 uppercase tracking-[0.15em] px-3 mb-2">{section}</p>
              <div className="space-y-0.5">
                {nav.filter(n => n.section === section).map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.to === '/'}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      clsx(
                        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150',
                        isActive
                          ? 'bg-emerald-500/10 text-emerald-400 border-l-[3px] border-emerald-400 ml-0 pl-[9px]'
                          : 'text-white/60 hover:text-white hover:bg-white/5 border-l-[3px] border-transparent',
                      )
                    }
                  >
                    <n.icon className="h-4 w-4" />
                    {n.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Agent Status */}
        <button
          onClick={() => setShowAgents(true)}
          className="mx-3 mb-3 px-3 py-2.5 rounded-lg bg-gradient-to-r from-emerald-500/10 to-teal-500/10 border border-emerald-500/20 hover:border-emerald-500/40 transition-all text-left group"
        >
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse-soft shadow-[0_0_8px_rgba(52,211,153,0.6)]" />
            <span className="text-[11px] font-semibold text-emerald-400 group-hover:text-emerald-300 transition-colors">4 Agents Online</span>
          </div>
        </button>

        {/* Theme Toggle */}
        <div className="mx-3 mb-3">
          <button
            onClick={toggle}
            className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg bg-orange-500/10 border border-orange-500/20 hover:border-orange-500/40 transition-all group"
          >
            <div className="flex items-center gap-2.5">
              {isDark ? <Sun className="h-4 w-4 text-orange-400" /> : <Moon className="h-4 w-4 text-orange-400" />}
              <span className="text-[11px] font-semibold text-orange-400">{isDark ? 'Light Mode' : 'Dark Mode'}</span>
            </div>
            <div className={clsx(
              'w-8 h-4.5 rounded-full p-0.5 transition-colors duration-200',
              isDark ? 'bg-orange-500' : 'bg-white/20',
            )}>
              <div className={clsx(
                'h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform duration-200',
                isDark ? 'translate-x-3.5' : 'translate-x-0',
              )} />
            </div>
          </button>
        </div>

        {/* User */}
        <div className="border-t border-white/5 px-4 py-3">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-[12px] font-bold text-white shadow-lg shadow-violet-500/20">
              {user?.full_name?.charAt(0)?.toUpperCase() || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-semibold text-white truncate">{user?.full_name}</p>
              <p className="text-[10px] text-white/40 capitalize truncate">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={() => { logout(); navigate('/login'); }}
            className="flex items-center gap-2 w-full px-2 py-2 rounded-lg text-[11px] text-white/40 hover:text-red-400 hover:bg-red-500/10 transition-all font-medium"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header (only shows hamburger on small screens) */}
        <header className="h-12 flex items-center px-6 lg:hidden shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-lg hover:bg-white/5 transition"
          >
            <Menu className={clsx('h-5 w-5', isDark ? 'text-white' : 'text-gray-700')} />
          </button>
        </header>

        {/* Page content */}
        <main className={clsx(
          'flex-1 overflow-y-auto transition-colors duration-300',
          isDark ? 'bg-[#0d1117]' : 'bg-[#f0f2f5]',
        )}>
          <div className="max-w-[1200px] mx-auto px-6 py-6">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Agent Status Modal */}
      {showAgents && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowAgents(false)}>
          <div
            className={clsx(
              'rounded-2xl border shadow-2xl w-full max-w-md mx-4 animate-scale-in overflow-hidden',
              isDark ? 'bg-[#161b22] border-white/10' : 'bg-white border-gray-200',
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={clsx('flex items-center justify-between px-5 py-4 border-b', isDark ? 'border-white/5' : 'border-gray-100')}>
              <div className="flex items-center gap-2.5">
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse-soft shadow-[0_0_8px_rgba(52,211,153,0.6)]" />
                <h2 className={clsx('text-[14px] font-bold', isDark ? 'text-white' : 'text-gray-900')}>Agent Status</h2>
              </div>
              <button onClick={() => setShowAgents(false)} className={clsx('p-1.5 rounded-lg transition', isDark ? 'hover:bg-white/5' : 'hover:bg-gray-100')}>
                <X className={clsx('h-4 w-4', isDark ? 'text-white/50' : 'text-gray-400')} />
              </button>
            </div>
            <div className="p-4 space-y-2.5 stagger-children">
              {agents.map((agent) => (
                <div key={agent.name} className={clsx(
                  'flex items-center gap-3 p-3.5 rounded-xl border transition-all hover:scale-[1.01]',
                  isDark ? 'bg-white/[0.02] border-white/5 hover:border-white/10' : 'bg-gray-50 border-gray-100 hover:border-gray-200',
                )}>
                  <div className={clsx('h-10 w-10 rounded-xl flex items-center justify-center', agent.bg)}>
                    <agent.icon className={clsx('h-5 w-5', agent.color)} />
                  </div>
                  <div className="flex-1">
                    <p className={clsx('text-[12px] font-bold', isDark ? 'text-white' : 'text-gray-900')}>{agent.name}</p>
                    <p className={clsx('text-[11px]', isDark ? 'text-white/50' : 'text-gray-500')}>{agent.desc}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
                    <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider">Active</span>
                  </div>
                </div>
              ))}
            </div>
            <div className={clsx('px-5 py-3 border-t', isDark ? 'border-white/5 bg-white/[0.02]' : 'border-gray-100 bg-gray-50')}>
              <p className={clsx('text-[10px] text-center font-mono', isDark ? 'text-white/30' : 'text-gray-400')}>All systems operational • Last checked: just now</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
