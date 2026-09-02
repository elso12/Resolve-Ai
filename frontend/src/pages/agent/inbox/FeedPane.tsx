import React, { useState } from 'react';
import { Search, Loader2, AlertCircle } from 'lucide-react';
import type { Ticket } from './types';

interface FeedPaneProps {
  tickets: Ticket[];
  selectedTicketId: string | number | null;
  onSelectTicket: (ticketId: string | number) => void;
  isLoading?: boolean;
}

export const FeedPane: React.FC<FeedPaneProps> = ({
  tickets,
  selectedTicketId,
  onSelectTicket,
  isLoading = false,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filteredTickets = tickets.filter((t) => {
    const ticketId = String(t.ticket_number || t.id).toLowerCase();
    const subject = (t.subject || '').toLowerCase();
    const cust = (t.customerName || '').toLowerCase();
    const term = searchTerm.toLowerCase();

    const matchesSearch = ticketId.includes(term) || subject.includes(term) || cust.includes(term);

    const matchesStatus =
      statusFilter === 'all' ||
      (t.status || '').toLowerCase() === statusFilter.toLowerCase();

    return matchesSearch && matchesStatus;
  });

  const formatRelativeTime = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffMinutes = Math.floor((now.getTime() - date.getTime()) / 60000);
      if (diffMinutes < 1) return 'Just now';
      if (diffMinutes < 60) return `${diffMinutes}m ago`;
      const diffHours = Math.floor(diffMinutes / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    } catch {
      return dateStr;
    }
  };

  const getPriorityBadge = (priority: string) => {
    const p = (priority || '').toLowerCase();
    if (p === 'critical' || p === 'urgent') {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-950/60 text-red-400 border border-red-800/60">
          Critical
        </span>
      );
    }
    if (p === 'high') {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-950/60 text-amber-400 border border-amber-800/60">
          High
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-neutral-800 text-neutral-400 border border-neutral-700">
        {p}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    const s = (status || '').toLowerCase();
    if (s === 'open') {
      return <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800">Open</span>;
    }
    if (s === 'in_progress') {
      return <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">In Progress</span>;
    }
    if (s === 'waiting_for_customer') {
      return <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">Waiting</span>;
    }
    if (s === 'resolved') {
      return <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-950 text-green-400 border border-green-800">Resolved</span>;
    }
    if (s === 'closed') {
      return <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400 border border-neutral-700">Closed</span>;
    }
    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400">{status}</span>;
  };

  return (
    <div className="w-80 border-r border-neutral-800 bg-neutral-900 flex flex-col h-full overflow-hidden shrink-0">
      {/* Search & Filter Header */}
      <div className="p-3 border-b border-neutral-800 bg-neutral-900 z-10 shrink-0 space-y-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-500" />
          <input
            type="text"
            placeholder="Search tickets..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 bg-neutral-800 border border-neutral-700 rounded-md focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm text-neutral-200 placeholder-neutral-500 transition-shadow"
          />
        </div>

        <div className="flex items-center gap-1 overflow-x-auto text-xs pb-1">
          {['all', 'open', 'in_progress', 'resolved'].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={`px-2 py-0.5 rounded text-[11px] capitalize whitespace-nowrap transition-colors ${
                statusFilter === st
                  ? 'bg-neutral-800 text-white font-medium border border-neutral-700'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              {st.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Ticket List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-neutral-400 flex flex-col items-center gap-2">
            <Loader2 size={20} className="animate-spin text-neutral-400" />
            <span>Loading tickets...</span>
          </div>
        ) : filteredTickets.length > 0 ? (
          <div className="divide-y divide-neutral-800">
            {filteredTickets.map((ticket) => {
              const displayId = ticket.ticket_number || String(ticket.id);
              const isSelected =
                String(selectedTicketId) === String(ticket.id) ||
                String(selectedTicketId) === String(ticket.ticket_number);

              return (
                <button
                  key={ticket.id}
                  onClick={() => onSelectTicket(ticket.id)}
                  className={`w-full text-left p-4 transition-colors relative ${
                    isSelected
                      ? 'bg-neutral-800 before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1 before:bg-blue-500'
                      : 'hover:bg-neutral-800/50'
                  }`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-semibold text-neutral-400">{displayId}</span>
                    <span className="text-xs text-neutral-500 whitespace-nowrap">
                      {formatRelativeTime(ticket.updated_at || ticket.created_at || ticket.updatedAt)}
                    </span>
                  </div>
                  <h3
                    className={`text-sm font-medium mb-1 line-clamp-1 ${
                      isSelected ? 'text-white' : 'text-neutral-200'
                    }`}
                  >
                    {ticket.subject}
                  </h3>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-neutral-400 line-clamp-1">
                      {ticket.customerName || `Customer #${ticket.customer_id || 'User'}`}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {getStatusBadge(ticket.status)}
                      {getPriorityBadge(ticket.priority)}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="p-8 text-center text-sm text-neutral-500 flex flex-col items-center gap-2">
            <AlertCircle size={24} className="text-neutral-600" />
            <span>No tickets found in this queue.</span>
          </div>
        )}
      </div>
    </div>
  );
};
