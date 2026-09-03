import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  Send,
  CheckCircle2,
  User,
  HeadphonesIcon,
  Loader2,
  Clock,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';

interface MessageSender {
  id: number;
  email: string;
  full_name: string;
  role: string;
}

interface MessageItem {
  id: number;
  ticket_id: number;
  sender_id: number;
  body: string;
  is_internal: boolean;
  created_at: string;
  sender?: MessageSender;
}

interface TicketDetail {
  id: number;
  ticket_number: string;
  subject: string;
  description: string;
  status: string;
  priority: string;
  category: string;
  created_at: string;
  updated_at: string;
  messages?: MessageItem[];
}

export const TicketDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const showSuccess = location.state?.showSuccess;
  const { user: currentUser } = useAuth();

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [replyText, setReplyText] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadTicketAndMessages = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);

    try {
      // 1. Fetch ticket details
      const ticketRes = await api.get(`/tickets/${id}`);
      setTicket(ticketRes.data);

      // 2. Fetch thread messages
      const messagesRes = await api.get(`/tickets/${id}/messages`);
      setMessages(messagesRes.data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Could not load ticket details. The ticket may not exist or access is restricted.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTicketAndMessages();
  }, [id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !replyText.trim() || isClosed || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const res = await api.post(`/tickets/${id}/messages`, {
        body: replyText.trim(),
        is_internal: false,
      });

      const newMessage: MessageItem = res.data;
      setMessages((prev) => [...prev, newMessage]);
      setReplyText('');

      // Auto-update ticket status in view (reopens/moves to in_progress upon customer reply)
      if (ticket && (ticket.status.toLowerCase() === 'waiting_for_customer' || ticket.status.toLowerCase() === 'resolved')) {
        setTicket({ ...ticket, status: 'in_progress' });
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit your reply. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isClosed = (ticket?.status || '').toLowerCase() === 'closed';

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
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-200 text-neutral-800">
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

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center">
        <Loader2 size={32} className="animate-spin text-primary mx-auto mb-4" />
        <p className="text-neutral-500 font-medium text-sm">Loading ticket conversation...</p>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <Link
          to="/help/tickets"
          className="inline-flex items-center text-sm font-medium text-neutral-500 hover:text-neutral-900 transition-colors mb-6"
        >
          <ArrowLeft size={16} className="mr-1" />
          Back to Tickets
        </Link>
        <div className="p-8 bg-red-50 border border-red-200 rounded-xl text-center">
          <AlertCircle size={36} className="text-red-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-red-900">Error Loading Ticket</h3>
          <p className="text-sm text-red-700 mt-1 max-w-md mx-auto">{error || 'Ticket not found.'}</p>
          <button
            onClick={loadTicketAndMessages}
            className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto pb-8">
      <div className="mb-6 flex items-center justify-between">
        <Link
          to="/help/tickets"
          className="inline-flex items-center text-sm font-medium text-neutral-500 hover:text-neutral-900 transition-colors"
        >
          <ArrowLeft size={16} className="mr-1" />
          Back to Tickets
        </Link>
        <div className="flex items-center gap-2">
          {getStatusBadge(ticket.status)}
          <span className="text-xs text-neutral-500 capitalize px-2 py-0.5 bg-neutral-100 rounded-md border border-neutral-200">
            {ticket.category}
          </span>
        </div>
      </div>

      {showSuccess && (
        <div className="mb-6 flex items-start gap-3 p-4 bg-green-50 text-green-800 rounded-xl shadow-sm border border-green-200">
          <CheckCircle2 size={20} className="shrink-0 mt-0.5 text-green-600" />
          <div className="text-sm">
            <p className="font-semibold text-green-900">Ticket submitted successfully!</p>
            <p className="mt-0.5 text-green-700">
              Your ticket reference is <strong className="font-mono">{ticket.ticket_number || id}</strong>. Our team
              will respond shortly.
            </p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-soft border border-neutral-200 overflow-hidden flex flex-col h-[75vh] min-h-[550px]">
        {/* Header */}
        <div className="p-5 border-b border-neutral-200 bg-neutral-50/80 flex items-start justify-between gap-4 shrink-0">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="text-xs font-mono font-semibold text-neutral-500">
                {ticket.ticket_number || `RSV-${ticket.id}`}
              </span>
              <span className="text-xs text-neutral-400">•</span>
              <span className="text-xs text-neutral-500">
                Created on {new Date(ticket.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            </div>
            <h1 className="text-lg font-bold text-neutral-900">{ticket.subject}</h1>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 bg-neutral-50/30">
          {/* Original Ticket Description */}
          {ticket.description && (
            <div className="flex gap-3 flex-row-reverse">
              <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white bg-primary shadow-sm font-semibold text-xs">
                <User size={15} />
              </div>
              <div className="flex flex-col items-end max-w-[80%]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold text-neutral-900">You (Original Request)</span>
                  <span className="text-[10px] text-neutral-500">
                    {new Date(ticket.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <div className="px-4 py-3 rounded-2xl text-xs sm:text-sm bg-neutral-100 text-neutral-900 rounded-tr-sm shadow-sm whitespace-pre-wrap leading-relaxed">
                  {ticket.description}
                </div>
              </div>
            </div>
          )}

          {/* Conversation Messages */}
          {messages.map((msg) => {
            const isCustomer =
              (msg.sender?.role === 'customer') ||
              (currentUser && msg.sender_id === Number(currentUser.id));
            const senderName = isCustomer ? 'You' : msg.sender?.full_name || 'Support Agent';

            return (
              <div key={msg.id} className={`flex gap-3 ${isCustomer ? 'flex-row-reverse' : ''}`}>
                <div
                  className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white shadow-sm font-semibold text-xs ${
                    isCustomer ? 'bg-primary' : 'bg-indigo-600'
                  }`}
                >
                  {isCustomer ? <User size={15} /> : <HeadphonesIcon size={15} />}
                </div>
                <div className={`flex flex-col ${isCustomer ? 'items-end' : 'items-start'} max-w-[80%]`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-neutral-900">{senderName}</span>
                    <span className="text-[10px] text-neutral-500">
                      {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div
                    className={`px-4 py-3 rounded-2xl text-xs sm:text-sm shadow-sm leading-relaxed whitespace-pre-wrap ${
                      isCustomer
                        ? 'bg-neutral-100 text-neutral-900 rounded-tr-sm'
                        : 'bg-indigo-50 text-neutral-900 border border-indigo-100 rounded-tl-sm'
                    }`}
                  >
                    {msg.body}
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Composer */}
        <div className="p-4 border-t border-neutral-200 bg-white shrink-0">
          {isClosed ? (
            <div className="text-center py-4 bg-neutral-50 rounded-xl border border-neutral-200">
              <p className="text-xs font-semibold text-neutral-700">This ticket is closed.</p>
              <p className="text-[11px] text-neutral-500 mt-0.5">
                If you still need help, please submit a new support request.
              </p>
            </div>
          ) : (
            <form onSubmit={handleReply} className="relative">
              <textarea
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Type your reply here..."
                rows={3}
                className="w-full pl-4 pr-12 py-3 border border-neutral-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent outline-none resize-none transition-shadow text-xs sm:text-sm leading-relaxed"
              />
              <button
                type="submit"
                disabled={!replyText.trim() || isSubmitting}
                className="absolute right-3 bottom-3 p-2 bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                aria-label="Send reply"
              >
                {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
