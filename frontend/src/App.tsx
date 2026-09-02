import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute, RoleBasedRoute } from './components/ProtectedRoute';
import { CustomerLayout } from './layouts/CustomerLayout';
import { AgentLayout } from './layouts/AgentLayout';
import { NewTicketPage } from './pages/customer/NewTicketPage';
import { MyTicketsPage } from './pages/customer/MyTicketsPage';
import { TicketDetailPage } from './pages/customer/TicketDetailPage';
import { KnowledgeBasePage } from './pages/customer/KnowledgeBasePage';
import { InboxPage } from './pages/agent/InboxPage';
import { AnalyticsPage } from './pages/manager/AnalyticsPage';


import { LoginPage } from './pages/auth/LoginPage';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/help" replace />} />

          {/* Customer Portal Alias Routes */}
          <Route path="/portal" element={<Navigate to="/help/tickets" replace />} />
          <Route path="/portal/tickets" element={<Navigate to="/help/tickets" replace />} />

          {/* Customer Routes */}
          <Route path="/help" element={<CustomerLayout />}>
            <Route index element={<KnowledgeBasePage />} />
            <Route
              path="tickets"
              element={
                <ProtectedRoute>
                  <MyTicketsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="tickets/new"
              element={
                <ProtectedRoute>
                  <NewTicketPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="tickets/:id"
              element={
                <ProtectedRoute>
                  <TicketDetailPage />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* Agent/Admin Routes */}
          <Route
            path="/agent"
            element={
              <RoleBasedRoute allowedRoles={['agent', 'admin']}>
                <AgentLayout />
              </RoleBasedRoute>
            }
          >
            <Route index element={<AnalyticsPage />} />
            <Route path="inbox" element={<InboxPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
