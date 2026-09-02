import React, { useState, useEffect, useCallback } from 'react';
import { QueuePane } from './inbox/QueuePane';
import { FeedPane } from './inbox/FeedPane';
import { WorkspacePane } from './inbox/WorkspacePane';
import type { Ticket, QueueType, TicketStatus } from './inbox/types';
import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export const InboxPage: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [activeQueue, setActiveQueue] = useState<QueueType>('all');
  const [selectedTicketId, setSelectedTicketId] = useState<string | number | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [isLoadingTickets, setIsLoadingTickets] = useState<boolean>(true);
  const [isSendingMessage, setIsSendingMessage] = useState<boolean>(false);

  // Fetch all tickets from backend
  const fetchTickets = useCallback(async (preserveSelection = true) => {
    setIsLoadingTickets(true);
    try {
      const res = await api.get('/tickets');
      const data: Ticket[] = res.data;
      setTickets(data);

      if (!preserveSelection || !selectedTicketId) {
        if (data.length > 0) {
          setSelectedTicketId(data[0].id);
        } else {
          setSelectedTicketId(null);
          setSelectedTicket(null);
        }
      }
    } catch (err) {
      console.error('Failed to fetch tickets from backend:', err);
    } finally {
      setIsLoadingTickets(false);
    }
  }, [selectedTicketId]);

  // Initial load
  useEffect(() => {
    fetchTickets(false);
  }, []);

  // Fetch full ticket details & messages when selectedTicketId changes
  useEffect(() => {
    if (!selectedTicketId) {
      setSelectedTicket(null);
      return;
    }

    let isMounted = true;
    const fetchTicketDetails = async () => {
      try {
        const res = await api.get(`/tickets/${selectedTicketId}`);
        if (isMounted) {
          setSelectedTicket(res.data);
        }
      } catch (err) {
        console.error(`Failed to load details for ticket ${selectedTicketId}:`, err);
        // Fallback to local ticket in state if API fails
        const fallback = tickets.find(
          (t) => String(t.id) === String(selectedTicketId) || t.ticket_number === String(selectedTicketId)
        );
        if (isMounted && fallback) {
          setSelectedTicket(fallback);
        }
      }
    };

    fetchTicketDetails();
    return () => {
      isMounted = false;
    };
  }, [selectedTicketId, tickets]);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedTicketId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Status update handler
  const handleUpdateStatus = async (ticketId: string | number, status: TicketStatus) => {
    try {
      const res = await api.patch(`/tickets/${ticketId}/status`, { status });
      const updatedTicket: Ticket = res.data;

      // Update both tickets list and active ticket
      setTickets((prev) =>
        prev.map((t) => (String(t.id) === String(ticketId) ? { ...t, status: updatedTicket.status } : t))
      );
      setSelectedTicket((prev) =>
        prev && String(prev.id) === String(ticketId) ? { ...prev, status: updatedTicket.status } : prev
      );
    } catch (err) {
      console.error('Failed to update status:', err);
      alert('Could not update status. Check that the transition is valid.');
    }
  };

  // Assignment handler
  const handleAssignTicket = async (ticketId: string | number, agentId: number) => {
    try {
      const res = await api.post(`/tickets/${ticketId}/assign`, { agent_id: agentId });
      const updatedTicket: Ticket = res.data;

      setTickets((prev) =>
        prev.map((t) =>
          String(t.id) === String(ticketId) ? { ...t, assigned_agent_id: updatedTicket.assigned_agent_id } : t
        )
      );
      setSelectedTicket((prev) =>
        prev && String(prev.id) === String(ticketId)
          ? { ...prev, assigned_agent_id: updatedTicket.assigned_agent_id }
          : prev
      );
    } catch (err) {
      console.error('Failed to assign ticket:', err);
      alert('Could not assign ticket.');
    }
  };

  // Send message or internal note handler
  const handleSendMessage = async (ticketId: string | number, text: string, isInternal: boolean) => {
    setIsSendingMessage(true);
    try {
      await api.post(`/tickets/${ticketId}/messages`, {
        body: text,
        is_internal: isInternal,
      });

      // Refetch ticket details to get fresh messages list with sender metadata
      const res = await api.get(`/tickets/${ticketId}`);
      setSelectedTicket(res.data);
    } catch (err) {
      console.error('Failed to post message:', err);
      alert('Failed to send message. Please try again.');
    } finally {
      setIsSendingMessage(false);
    }
  };

  // Dynamic ticket counts per filter for QueuePane
  const queueCounts = React.useMemo(() => {
    const currentUserId = currentUser?.id ? Number(currentUser.id) : null;
    return {
      all: tickets.length,
      assigned: tickets.filter((t) => currentUserId !== null && Number(t.assigned_agent_id) === currentUserId).length,
      unassigned: tickets.filter((t) => !t.assigned_agent_id).length,
      high_priority: tickets.filter(
        (t) =>
          (t.priority || '').toLowerCase() === 'high' ||
          (t.priority || '').toLowerCase() === 'critical' ||
          t.sla_first_response_breached ||
          t.sla_resolution_breached
      ).length,
      resolved: tickets.filter(
        (t) => (t.status || '').toLowerCase() === 'resolved' || (t.status || '').toLowerCase() === 'closed'
      ).length,
    };
  }, [tickets, currentUser]);

  // Filtered tickets according to activeQueue
  const filteredTickets = React.useMemo(() => {
    const currentUserId = currentUser?.id ? Number(currentUser.id) : null;
    return tickets.filter((t) => {
      const status = (t.status || '').toLowerCase();
      const priority = (t.priority || '').toLowerCase();

      if (activeQueue === 'all') return true;
      if (activeQueue === 'resolved') return status === 'resolved' || status === 'closed';
      if (activeQueue === 'high_priority') {
        return priority === 'high' || priority === 'critical' || t.sla_first_response_breached || t.sla_resolution_breached;
      }
      if (activeQueue === 'assigned') {
        return currentUserId !== null && Number(t.assigned_agent_id) === currentUserId;
      }
      if (activeQueue === 'unassigned') {
        return !t.assigned_agent_id;
      }
      return true;
    });
  }, [tickets, activeQueue, currentUser]);

  return (
    <div className="flex h-full w-full overflow-hidden bg-neutral-950">
      <QueuePane activeQueue={activeQueue} counts={queueCounts} onSelectQueue={setActiveQueue} />
      <FeedPane
        tickets={filteredTickets}
        selectedTicketId={selectedTicketId}
        onSelectTicket={setSelectedTicketId}
        isLoading={isLoadingTickets}
      />
      <WorkspacePane
        ticket={selectedTicket}
        onUpdateStatus={handleUpdateStatus}
        onAssignTicket={handleAssignTicket}
        onSendMessage={handleSendMessage}
        isSendingMessage={isSendingMessage}
      />
    </div>
  );
};
