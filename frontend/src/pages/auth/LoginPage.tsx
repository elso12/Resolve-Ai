import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  HeadphonesIcon,
  Lock,
  Mail,
  User as UserIcon,
  Building2,
  Shield,
  ArrowRight,
  Loader2,
  AlertCircle,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import { useAuth, type UserRole } from '../../context/AuthContext';
import api from '../../services/api';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [orgName, setOrgName] = useState('');
  const [selectedRole, setSelectedRole] = useState<'customer' | 'agent'>('customer');

  const redirectByRole = (role: string) => {
    // Check if user was navigated here from a protected route
    const fromPath = (location.state as any)?.from?.pathname;
    if (fromPath && fromPath !== '/login') {
      if (role === 'customer' && !fromPath.startsWith('/agent')) {
        navigate(fromPath, { replace: true });
        return;
      }
      if (role !== 'customer') {
        navigate(fromPath, { replace: true });
        return;
      }
    }

    if (role === 'customer') {
      navigate('/portal/tickets', { replace: true });
    } else if (role === 'manager') {
      navigate('/manager/analytics', { replace: true });
    } else {
      // agent, admin
      navigate('/agent/inbox', { replace: true });
    }
  };

  const handleQuickDemoLogin = async (demoEmail: string, demoPassword: string, targetPath: string) => {
    setEmail(demoEmail);
    setPassword(demoPassword);
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsLoading(true);

    try {
      // 1. Authenticate with backend
      const loginRes = await api.post('/auth/login', {
        email: demoEmail.trim(),
        password: demoPassword,
      });

      const { access_token } = loginRes.data;

      // 2. Fetch authenticated profile
      const profileRes = await api.get('/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      const userData = {
        id: String(profileRes.data.id),
        email: profileRes.data.email,
        full_name: profileRes.data.full_name,
        role: profileRes.data.role as UserRole,
      };

      // 3. Update Auth Context
      login(access_token, userData);

      // 4. Navigate to the target demo route
      navigate(targetPath, { replace: true });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else if (Array.isArray(detail)) {
        setErrorMessage(detail.map((d: any) => d.msg || d).join(', '));
      } else {
        setErrorMessage('Failed to sign in with demo credentials. Please check backend connection.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsLoading(true);

    try {
      // 1. Authenticate with backend
      const loginRes = await api.post('/auth/login', {
        email: email.trim(),
        password,
      });

      const { access_token } = loginRes.data;

      // 2. Fetch authenticated profile
      const profileRes = await api.get('/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      const userData = {
        id: String(profileRes.data.id),
        email: profileRes.data.email,
        full_name: profileRes.data.full_name,
        role: profileRes.data.role as UserRole,
      };

      // 3. Update Auth Context
      login(access_token, userData);

      // 4. Redirect based on role
      redirectByRole(userData.role);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else if (Array.isArray(detail)) {
        setErrorMessage(detail.map((d: any) => d.msg || d).join(', '));
      } else {
        setErrorMessage('Failed to sign in. Please verify your credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsLoading(true);

    try {
      // 1. Register with backend
      await api.post('/auth/register', {
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        organization_name: orgName.trim() || `${fullName.trim() || 'User'}'s Organization`,
        role: selectedRole,
      });

      setSuccessMessage('Account created successfully! Signing in...');

      // 2. Auto-login immediately
      const loginRes = await api.post('/auth/login', {
        email: email.trim(),
        password,
      });

      const { access_token } = loginRes.data;

      // 3. Fetch user profile
      const profileRes = await api.get('/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      const userData = {
        id: String(profileRes.data.id),
        email: profileRes.data.email,
        full_name: profileRes.data.full_name,
        role: profileRes.data.role as UserRole,
      };

      login(access_token, userData);
      redirectByRole(userData.role);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else if (Array.isArray(detail)) {
        setErrorMessage(detail.map((d: any) => d.msg || d).join(', '));
      } else {
        setErrorMessage('Registration failed. Please check the inputs and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-neutral-100 selection:bg-neutral-800">
      {/* Background Decorative Glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-tr from-indigo-500/10 via-purple-500/10 to-transparent blur-3xl pointer-events-none rounded-full" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        {/* Brand Header */}
        <div className="flex items-center justify-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-white font-bold text-lg">
            <HeadphonesIcon size={22} />
          </div>
          <span className="text-2xl font-bold tracking-tight text-white">ResolveAI</span>
        </div>

        <h2 className="text-center text-xl font-semibold text-neutral-200">
          {mode === 'signin' ? 'Welcome back to ResolveAI' : 'Create your ResolveAI account'}
        </h2>
        <p className="mt-1 text-center text-sm text-neutral-400">
          {mode === 'signin'
            ? 'Access your customer tickets or agent workspace'
            : 'Get started with AI-orchestrated support workflows'}
        </p>

        {/* Dual-Mode Toggle Pills */}
        <div className="mt-6 p-1 bg-neutral-900 border border-neutral-800 rounded-xl flex items-center">
          <button
            type="button"
            onClick={() => {
              setMode('signin');
              setErrorMessage(null);
            }}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              mode === 'signin'
                ? 'bg-neutral-800 text-white shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('signup');
              setErrorMessage(null);
            }}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              mode === 'signup'
                ? 'bg-neutral-800 text-white shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Create Account
          </button>
        </div>
      </div>

      {/* Main Form Card */}
      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4 sm:px-0">
        <div className="bg-neutral-900/90 backdrop-blur-md py-8 px-6 shadow-2xl rounded-2xl border border-neutral-800 sm:px-10">
          {/* Error Alert */}
          {errorMessage && (
            <div className="mb-6 p-4 rounded-xl bg-red-950/50 border border-red-800/60 text-red-300 text-sm flex items-start gap-3">
              <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />
              <div className="flex-1">{errorMessage}</div>
            </div>
          )}

          {/* Success Alert */}
          {successMessage && (
            <div className="mb-6 p-4 rounded-xl bg-green-950/50 border border-green-800/60 text-green-300 text-sm flex items-start gap-3">
              <CheckCircle2 size={18} className="text-green-400 shrink-0 mt-0.5" />
              <div className="flex-1">{successMessage}</div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={mode === 'signin' ? handleSignIn : handleSignUp} className="space-y-4">
            {mode === 'signup' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                    Full Name
                  </label>
                  <div className="relative">
                    <UserIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                    <input
                      type="text"
                      required
                      placeholder="e.g. Sarah Jenkins"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full pl-10 pr-3 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                    Organization / Company Name
                  </label>
                  <div className="relative">
                    <Building2 size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                    <input
                      type="text"
                      placeholder="e.g. Acme Corporation"
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      className="w-full pl-10 pr-3 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                    />
                  </div>
                </div>

                {/* Role Selector */}
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                    Select Your Role
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedRole('customer')}
                      className={`p-2.5 rounded-lg border text-left transition-all flex items-center gap-2.5 ${
                        selectedRole === 'customer'
                          ? 'border-indigo-500 bg-indigo-950/30 text-white'
                          : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:text-neutral-200'
                      }`}
                    >
                      <UserIcon size={16} className={selectedRole === 'customer' ? 'text-indigo-400' : 'text-neutral-500'} />
                      <div>
                        <div className="text-xs font-medium">Customer</div>
                        <div className="text-[10px] text-neutral-400">Submit requests</div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setSelectedRole('agent')}
                      className={`p-2.5 rounded-lg border text-left transition-all flex items-center gap-2.5 ${
                        selectedRole === 'agent'
                          ? 'border-indigo-500 bg-indigo-950/30 text-white'
                          : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:text-neutral-200'
                      }`}
                    >
                      <Shield size={16} className={selectedRole === 'agent' ? 'text-indigo-400' : 'text-neutral-500'} />
                      <div>
                        <div className="text-xs font-medium">Support Agent</div>
                        <div className="text-[10px] text-neutral-400">Agent inbox</div>
                      </div>
                    </button>
                  </div>
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                Work Email Address
              </label>
              <div className="relative">
                <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-medium text-neutral-300">
                  Password
                </label>
                {mode === 'signup' && (
                  <span className="text-[10px] text-neutral-400">Min 8 chars, 1 uppercase, 1 number</span>
                )}
              </div>
              <div className="relative">
                <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 bg-neutral-950 border border-neutral-800 rounded-lg text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 flex items-center justify-center gap-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <span>{mode === 'signin' ? 'Sign In to Workspace' : 'Complete Registration'}</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Access Card */}
          <div className="mt-8 pt-6 border-t border-neutral-800">
            <div className="flex items-center justify-between mb-3.5">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-amber-400" />
                <span className="text-xs font-semibold text-neutral-200 uppercase tracking-wider">Quick Demo Access</span>
              </div>
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-neutral-800 text-neutral-400 border border-neutral-700">
                1-Click Instant Login
              </span>
            </div>

            <div className="space-y-2.5">
              {/* Button 1: 1-Click Demo Agent */}
              <button
                type="button"
                disabled={isLoading}
                onClick={() => handleQuickDemoLogin('agent@resolveai.dev', 'Password123!', '/agent/inbox')}
                className="w-full group flex items-center justify-between p-3 rounded-xl border border-neutral-800/90 bg-neutral-950/70 hover:bg-neutral-800/80 hover:border-blue-500/50 transition-all text-left cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-blue-950/60 border border-blue-800/60 flex items-center justify-center text-sm shrink-0">
                    👤
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-neutral-100 group-hover:text-white truncate">
                      👤 1-Click Demo Agent
                    </div>
                    <div className="text-[11px] text-neutral-400 font-mono truncate">
                      agent@resolveai.dev
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-blue-950 text-blue-300 border border-blue-800">
                    AGENT
                  </span>
                  <span className="text-xs text-neutral-500 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all">
                    →
                  </span>
                </div>
              </button>

              {/* Button 2: 1-Click Demo Customer */}
              <button
                type="button"
                disabled={isLoading}
                onClick={() => handleQuickDemoLogin('customer@resolveai.dev', 'Password123!', '/portal/tickets')}
                className="w-full group flex items-center justify-between p-3 rounded-xl border border-neutral-800/90 bg-neutral-950/70 hover:bg-neutral-800/80 hover:border-purple-500/50 transition-all text-left cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-purple-950/60 border border-purple-800/60 flex items-center justify-center text-sm shrink-0">
                    🛍️
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-neutral-100 group-hover:text-white truncate">
                      🛍️ 1-Click Demo Customer
                    </div>
                    <div className="text-[11px] text-neutral-400 font-mono truncate">
                      customer@resolveai.dev
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-purple-950 text-purple-300 border border-purple-800">
                    CUSTOMER
                  </span>
                  <span className="text-xs text-neutral-500 group-hover:text-purple-400 group-hover:translate-x-0.5 transition-all">
                    →
                  </span>
                </div>
              </button>

              {/* Button 3: 1-Click Demo Manager */}
              <button
                type="button"
                disabled={isLoading}
                onClick={() => handleQuickDemoLogin('manager@resolveai.dev', 'Password123!', '/manager/analytics')}
                className="w-full group flex items-center justify-between p-3 rounded-xl border border-neutral-800/90 bg-neutral-950/70 hover:bg-neutral-800/80 hover:border-emerald-500/50 transition-all text-left cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-emerald-950/60 border border-emerald-800/60 flex items-center justify-center text-sm shrink-0">
                    📊
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-neutral-100 group-hover:text-white truncate">
                      📊 1-Click Demo Manager
                    </div>
                    <div className="text-[11px] text-neutral-400 font-mono truncate">
                      manager@resolveai.dev
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-emerald-950 text-emerald-300 border border-emerald-800">
                    MANAGER
                  </span>
                  <span className="text-xs text-neutral-500 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all">
                    →
                  </span>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
