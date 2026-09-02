import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Search,
  Plus,
  Clock,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Inbox,
  FolderOpen,
} from 'lucide-react';
import api from '../../services/api';

interface TicketItem {
  id: number;
  ticket_number: string;
  subject: string;
  description: string;
  status: string;
  priority: string;
  category: string;
  created_at: string;
  updated_at: string;
}

export const MyTicketsPage: React.FC = () => {
  const location = useLocation();
  const showSuccess = location.state?.showSuccess;

  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');

  const fetchTickets = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get('/tickets');
      setTickets(res.data);
    } catch (err: any) {
      console.error('Failed to load tickets:', err);
      setError(
        err.response?.data?.detail || 'Unable to load your tickets. Please check your connection and try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, []);

  const filteredTickets = tickets.filter((ticket) => {
    const term = searchTerm.toLowerCase();
    const matchesSearch =
      ticket.subject.toLowerCase().includes(term) ||
      ticket.ticket_number.toLowerCase().includes(term) ||
      String(ticket.id).includes(term);

    const s = (ticket.status || '').toLowerCase();
    const filter = statusFilter.toLowerCase();
    let matchesStatus = filter === 'all';
    if (filter === 'open') {
      matchesStatus = s === 'open' || s === 'in_progress' || s === 'waiting_for_customer' || s === 'assigned';
    } else if (filter === 'resolved') {
      matchesStatus = s === 'resolved' || s === 'closed';
    }

    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    const s = (status || '').toLowerCase();
    switch (s) {
      case 'open':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            <Clock size={12} /> Open
          </span>
        );
      case 'in_progress':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-200">
            <RefreshCw size={12} className="animate-spin" /> In Progress
          </span>
        );
      case 'waiting_for_customer':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            Waiting on You
          </span>
        );
      case 'resolved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-800 border border-green-200">
            <CheckCircle2 size={12} /> Resolved
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-600 border border-neutral-200">
            Closed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-800">
            {status}
          </span>
        );
    }
  };

  const getPriorityColor = (priority: string) => {
    const p = (priority || '').toLowerCase();
    switch (p) {
      case 'critical':
        return 'text-red-700 font-bold bg-red-50 px-2 py-0.5 rounded border border-red-200';
      case 'high':
        return 'text-orange-700 font-semibold bg-orange-50 px-2 py-0.5 rounded border border-orange-200';
      case 'medium':
        return 'text-neutral-700 font-medium';
      case 'low':
        return 'text-neutral-500 text-xs';
      default:
        return 'text-neutral-600';
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  // Live counts
  const totalCount = tickets.length;
  const openCount = tickets.filter((t) => {
    const s = (t.status || '').toLowerCase();
    return s !== 'resolved' && s !== 'closed';
  }).length;
  const resolvedCount = tickets.filter((t) => {
    const s = (t.status || '').toLowerCase();
    return s === 'resolved' || s === 'closed';
  }).length;

  return (
    <div className="max-w-5xl mx-auto pb-12">
      {showSuccess && (
        <div className="mb-6 flex items-start gap-3 p-4 bg-green-50 text-green-800 rounded-xl shadow-sm border border-green-200">
          <CheckCircle2 size={20} className="shrink-0 mt-0.5 text-green-600" />
          <div className="text-sm">
            <p className="font-semibold text-green-900">Ticket submitted successfully!</p>
            <p className="mt-0.5 text-green-700">
              Your support request has been registered and our team will get back to you promptly.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6 flex items-center justify-between p-4 bg-red-50 text-red-800 rounded-xl shadow-sm border border-red-200 text-sm">
          <div className="flex items-center gap-2">
            <AlertCircle size={18} className="text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchTickets}
            className="text-xs font-semibold px-3 py-1 bg-red-100 hover:bg-red-200 text-red-900 rounded-md transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Header & Stats Cards */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">My Support Tickets</h1>
          <p className="text-sm text-neutral-500 mt-1">Track issues, updates, and communications with our support specialists.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchTickets}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-neutral-300 rounded-lg text-sm text-neutral-700 hover:bg-neutral-50 transition-colors disabled:opacity-50"
            title="Refresh ticket list"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <Link
            to="/help/tickets/new"
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-semibold transition-colors shadow-sm whitespace-nowrap"
          >
            <Plus size={16} />
            <span>New Request</span>
          </Link>
        </div>
      </div>

      {/* Stat Badges */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-4 rounded-xl border border-neutral-200 shadow-sm flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <FolderOpen size={20} />
          </div>
          <div>
            <p className="text-xs text-neutral-500 font-medium">Total Tickets</p>
            <p className="text-xl font-bold text-neutral-900">{totalCount}</p>
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-neutral-200 shadow-sm flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
            <Clock size={20} />
          </div>
          <div>
            <p className="text-xs text-neutral-500 font-medium">Active / Open</p>
            <p className="text-xl font-bold text-neutral-900">{openCount}</p>
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-neutral-200 shadow-sm flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center text-green-600">
            <CheckCircle2 size={20} />
          </div>
          <div>
            <p className="text-xs text-neutral-500 font-medium">Resolved</p>
            <p className="text-xl font-bold text-neutral-900">{resolvedCount}</p>
          </div>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="bg-white rounded-xl shadow-soft border border-neutral-200 overflow-hidden">
        {/* Filters */}
        <div className="p-4 border-b border-neutral-200 flex flex-col sm:flex-row gap-4 items-center justify-between bg-neutral-50/50">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
            <input
              type="text"
              placeholder="Search by ID or subject..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-neutral-900 focus:border-transparent outline-none text-sm bg-white transition-shadow"
            />
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <span className="text-sm font-medium text-neutral-700 whitespace-nowrap">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full sm:w-auto px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-neutral-900 focus:border-transparent outline-none text-sm bg-white transition-shadow"
            >
              <option value="All">All Statuses ({totalCount})</option>
              <option value="Open">Active / Open ({openCount})</option>
              <option value="Resolved">Resolved ({resolvedCount})</option>
            </select>
          </div>
        </div>

        {/* Loading Skeletons */}
        {isLoading ? (
          <div className="p-6 space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse flex items-center justify-between p-4 bg-neutral-50 rounded-lg">
                <div className="space-y-2 flex-1 max-w-md">
                  <div className="h-4 bg-neutral-200 rounded w-3/4"></div>
                  <div className="h-3 bg-neutral-200 rounded w-1/4"></div>
                </div>
                <div className="h-6 bg-neutral-200 rounded-full w-20"></div>
                <div className="h-4 bg-neutral-200 rounded w-16 hidden sm:block"></div>
                <div className="h-4 bg-neutral-200 rounded w-24 hidden sm:block"></div>
              </div>
            ))}
          </div>
        ) : filteredTickets.length > 0 ? (
          /* Table View */
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[600px]">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  <th className="px-6 py-4">Ticket</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Priority</th>
                  <th className="px-6 py-4">Category</th>
                  <th className="px-6 py-4">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {filteredTickets.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-neutral-50/70 transition-colors group">
                    <td className="px-6 py-4">
                      <Link to={`/help/tickets/${ticket.id}`} className="block">
                        <span className="text-sm font-semibold text-neutral-900 group-hover:text-primary transition-colors line-clamp-1">
                          {ticket.subject}
                        </span>
                        <span className="text-xs font-mono text-neutral-500 mt-1 block">
                          {ticket.ticket_number || `RSV-${ticket.id}`}
                        </span>
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">{getStatusBadge(ticket.status)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={getPriorityColor(ticket.priority)}>
                        {ticket.priority.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-xs text-neutral-600 capitalize">
                      {ticket.category}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-xs text-neutral-500">
                      {formatDate(ticket.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* Empty State */
          <div className="p-12 text-center">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-neutral-100 text-neutral-400 mb-4">
              <Inbox size={28} />
            </div>
            <h3 className="text-lg font-semibold text-neutral-900">No tickets found</h3>
            <p className="text-sm text-neutral-500 mt-1 max-w-sm mx-auto">
              {searchTerm || statusFilter !== 'All'
                ? "We couldn't find any tickets matching your search criteria."
                : 'You have not submitted any support tickets yet.'}
            </p>
            <div className="mt-6">
              <Link
                to="/help/tickets/new"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors shadow-sm"
              >
                <Plus size={16} />
                <span>Create your first ticket</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
