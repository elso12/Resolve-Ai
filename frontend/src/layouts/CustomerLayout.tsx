import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { HeadphonesIcon, LogOut, User as UserIcon } from 'lucide-react';

export const CustomerLayout: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-surface-dim">
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="bg-primary text-white p-1.5 rounded-md">
              <HeadphonesIcon size={20} />
            </div>
            <span className="font-semibold text-lg tracking-tight">Resolve-AI Help Center</span>
          </div>
          
          <nav className="hidden md:flex items-center gap-6">
            <Link to="/help" className="text-sm font-medium text-neutral-600 hover:text-primary transition-colors">
              Knowledge Base
            </Link>
            <Link to="/help/tickets" className="text-sm font-medium text-neutral-600 hover:text-primary transition-colors">
              My Tickets
            </Link>
          </nav>

          <div className="flex items-center gap-4">
            {user ? (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-sm font-medium text-neutral-700">
                  <div className="w-8 h-8 rounded-full bg-neutral-100 border border-neutral-200 flex items-center justify-center">
                    <UserIcon size={16} className="text-neutral-500" />
                  </div>
                  <span className="hidden sm:inline-block">{user.full_name}</span>
                </div>
                <button
                  onClick={logout}
                  className="text-neutral-500 hover:text-neutral-900 transition-colors"
                  aria-label="Logout"
                >
                  <LogOut size={18} />
                </button>
              </div>
            ) : (
              <Link to="/login" className="text-sm font-medium text-primary hover:text-neutral-600 transition-colors">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8">
        <Outlet />
      </main>
      
      <footer className="py-6 border-t border-neutral-200 mt-auto text-center text-sm text-neutral-500">
        <p>&copy; {new Date().getFullYear()} Resolve-AI. All rights reserved.</p>
      </footer>
    </div>
  );
};
