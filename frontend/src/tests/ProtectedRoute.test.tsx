import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute, RoleBasedRoute } from '../components/ProtectedRoute';
import * as AuthContextModule from '../context/AuthContext';

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('Route Protection Component Suite', () => {
  const useAuthMock = vi.spyOn(AuthContextModule, 'useAuth');

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('ProtectedRoute', () => {
    it('redirects unauthenticated users to /login', () => {
      useAuthMock.mockReturnValue({
        isAuthenticated: false,
        user: null,
        token: null,
        role: null,
        login: vi.fn(),
        logout: vi.fn(),
      });

      render(
        <MemoryRouter initialEntries={['/protected']}>
          <Routes>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route
              path="/protected"
              element={
                <ProtectedRoute>
                  <div>Secret Content</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Login Page')).toBeInTheDocument();
      expect(screen.queryByText('Secret Content')).not.toBeInTheDocument();
    });

    it('renders children when user is authenticated', () => {
      useAuthMock.mockReturnValue({
        isAuthenticated: true,
        user: { id: '1', email: 'user@resolveai.com', full_name: 'Test User', role: 'customer' },
        token: 'valid-jwt-token',
        role: 'customer',
        login: vi.fn(),
        logout: vi.fn(),
      });

      render(
        <MemoryRouter initialEntries={['/protected']}>
          <Routes>
            <Route path="/login" element={<div>Login Page</div>} />
            <Route
              path="/protected"
              element={
                <ProtectedRoute>
                  <div>Secret Content</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Secret Content')).toBeInTheDocument();
    });
  });

  describe('RoleBasedRoute', () => {
    it('blocks unauthorized role and redirects to root /', () => {
      useAuthMock.mockReturnValue({
        isAuthenticated: true,
        user: { id: '1', email: 'cust@resolveai.com', full_name: 'Customer Bob', role: 'customer' },
        token: 'valid-jwt-token',
        role: 'customer',
        login: vi.fn(),
        logout: vi.fn(),
      });

      render(
        <MemoryRouter initialEntries={['/agent/inbox']}>
          <Routes>
            <Route path="/" element={<div>Default Home</div>} />
            <Route
              path="/agent/inbox"
              element={
                <RoleBasedRoute allowedRoles={['agent', 'admin']}>
                  <div>Agent Workspace</div>
                </RoleBasedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Default Home')).toBeInTheDocument();
      expect(screen.queryByText('Agent Workspace')).not.toBeInTheDocument();
    });

    it('allows authorized role to access route', () => {
      useAuthMock.mockReturnValue({
        isAuthenticated: true,
        user: { id: '2', email: 'agent@resolveai.com', full_name: 'Agent Alice', role: 'agent' },
        token: 'valid-jwt-token',
        role: 'agent',
        login: vi.fn(),
        logout: vi.fn(),
      });

      render(
        <MemoryRouter initialEntries={['/agent/inbox']}>
          <Routes>
            <Route path="/" element={<div>Default Home</div>} />
            <Route
              path="/agent/inbox"
              element={
                <RoleBasedRoute allowedRoles={['agent', 'admin']}>
                  <div>Agent Workspace</div>
                </RoleBasedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Agent Workspace')).toBeInTheDocument();
    });
  });
});
