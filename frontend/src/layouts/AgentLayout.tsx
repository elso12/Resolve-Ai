import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Inbox, Activity, Settings, Bell, Search, LayoutDashboard, Workflow } from 'lucide-react';

export const AgentLayout: React.FC = () => {
  const { user, logout } = useAuth();

  const navItems = [
    { name: 'Dashboard', path: '/agent', icon: LayoutDashboard },
    { name: 'Inbox', path: '/agent/inbox', icon: Inbox },
    { name: 'Analytics', path: '/agent/analytics', icon: Activity },
    { name: 'Automations', path: '/agent/automations', icon: Workflow },
    { name: 'Settings', path: '/agent/settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen flex h-screen overflow-hidden bg-neutral-900 text-neutral-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-neutral-800 bg-neutral-950 flex flex-col">
        <div className="h-14 flex items-center px-4 border-b border-neutral-800">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-neutral-800 flex items-center justify-center border border-neutral-700">
              <span className="text-xs font-bold text-white">R</span>
            </div>
            <span className="font-semibold text-sm tracking-wide">Workspace</span>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <div className="text-xs font-medium text-neutral-500 mb-2 px-2 uppercase tracking-wider">Main</div>
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              end={item.path === '/agent'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-neutral-800 text-white'
                    : 'text-neutral-400 hover:text-white hover:bg-neutral-800/50'
                }`
              }
            >
              <item.icon size={16} />
              {item.name}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-neutral-800">
          <div className="flex items-center gap-3 w-full">
            <div className="w-8 h-8 rounded-full bg-neutral-800 border border-neutral-700 flex items-center justify-center text-xs font-medium text-white relative">
              {user?.full_name?.charAt(0) || 'A'}
              <div className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-500 rounded-full border-2 border-neutral-950"></div>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.full_name}</p>
              <p className="text-xs text-neutral-500 truncate capitalize">{user?.role}</p>
            </div>
            <button onClick={logout} className="text-neutral-500 hover:text-white transition-colors" title="Logout">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-neutral-800 flex items-center justify-between px-6 bg-neutral-900/50 backdrop-blur-sm z-10 sticky top-0">
          <div className="flex items-center gap-4 flex-1">
            <div className="relative w-full max-w-md hidden sm:block">
              <Search className="absolute left-2.5 top-2 h-4 w-4 text-neutral-500" />
              <input
                type="text"
                placeholder="Search tickets, customers..."
                className="w-full bg-neutral-800 border border-neutral-700 rounded-md py-1.5 pl-9 pr-3 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-600 focus:border-neutral-600 transition-shadow"
              />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button className="text-neutral-400 hover:text-white transition-colors relative">
              <Bell size={18} />
              <span className="absolute 0 0 w-2 h-2 bg-blue-500 rounded-full"></span>
            </button>
          </div>
        </header>
        <div className="flex-1 overflow-auto bg-neutral-900">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
