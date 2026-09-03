import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkspacePane } from '../pages/agent/inbox/WorkspacePane';
import type { Ticket } from '../pages/agent/inbox/types';

// Mock dependencies
vi.mock('../services/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn().mockReturnValue({
    user: { id: '1', email: 'current@resolveai.com', full_name: 'Current Agent', role: 'agent' },
    isAuthenticated: true,
  }),
}));

const mockUseTicketSocket = vi.fn();
vi.mock('../hooks/useTicketSocket', () => ({
  useTicketSocket: (args: unknown) => mockUseTicketSocket(args),
}));

describe('WorkspacePane Component - Agent Collision Detection', () => {
  const mockTicket: Ticket = {
    id: 101,
    ticket_number: 'RSV-2026-TEST',
    subject: 'Cannot login to account',
    description: 'User reported password reset error',
    status: 'open',
    priority: 'high',
    category: 'account',
    customer_id: 1,
    assigned_agent_id: null,
    organization_id: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    customerName: 'John Doe',
    customerEmail: 'customer@acme.com',
    customerPlan: 'Enterprise',
    messages: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Agent Collision Warning banner when collision state is active', async () => {
    mockUseTicketSocket.mockReturnValue({
      activeViewers: [
        { user_id: 2, full_name: 'Agent Sarah', email: 'sarah@resolveai.com' },
      ],
      typingAgents: [],
      sendTyping: vi.fn(),
    });

    render(
      <WorkspacePane
        ticket={mockTicket}
        onUpdateStatus={vi.fn()}
        onAssignTicket={vi.fn()}
        onSendMessage={vi.fn()}
      />
    );

    // Verify collision warning banner appears
    expect(await screen.findByText(/Agent Collision Warning:/i)).toBeInTheDocument();
    expect(screen.getByText('Agent Sarah')).toBeInTheDocument();
    expect(screen.getByText(/is currently viewing this ticket/i)).toBeInTheDocument();
  });

  it('does not render Collision Warning banner when no other agents are viewing', async () => {
    mockUseTicketSocket.mockReturnValue({
      activeViewers: [],
      typingAgents: [],
      sendTyping: vi.fn(),
    });

    render(
      <WorkspacePane
        ticket={mockTicket}
        onUpdateStatus={vi.fn()}
        onAssignTicket={vi.fn()}
        onSendMessage={vi.fn()}
      />
    );

    expect(screen.queryByText(/Agent Collision Warning:/i)).not.toBeInTheDocument();
    expect(await screen.findByText(/User reported password reset error/i)).toBeInTheDocument();
  });
});
