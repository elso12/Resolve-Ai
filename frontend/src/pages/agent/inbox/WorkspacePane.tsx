import React, { useState, useEffect } from 'react';
import type { Ticket, TicketStatus, Message } from './types';
import {
  Lock,
  Send,
  Sparkles,
  X,
  UserPlus,
  Loader2,
  Inbox as InboxIcon,
} from 'lucide-react';
import api from '../../../services/api';
import { useAuth } from '../../../context/AuthContext';

interface WorkspacePaneProps {
  ticket: Ticket | null;
  onUpdateStatus: (ticketId: string | number, status: TicketStatus) => Promise<void> | void;
  onAssignTicket: (ticketId: string | number, agentId: number) => Promise<void> | void;
  onSendMessage: (ticketId: string | number, text: string, isInternal: boolean) => Promise<void> | void;
  isSendingMessage?: boolean;
}

const ALLOWED_STATUS_OPTIONS: Record<TicketStatus, TicketStatus[]> = {
  open: ['open', 'assigned', 'in_progress', 'closed'],
  assigned: ['assigned', 'in_progress', 'waiting_for_customer', 'resolved', 'closed'],
  in_progress: ['in_progress', 'waiting_for_customer', 'resolved', 'closed'],
  waiting_for_customer: ['waiting_for_customer', 'in_progress', 'resolved', 'closed'],
  resolved: ['resolved', 'in_progress', 'closed'],
  closed: ['closed'],
};

const STATUS_LABELS: Record<TicketStatus, string> = {
  open: 'Open',
  assigned: 'Assigned',
  in_progress: 'In Progress',
  waiting_for_customer: 'Waiting on Customer',
  resolved: 'Resolved',
  closed: 'Closed',
};

export const WorkspacePane: React.FC<WorkspacePaneProps> = ({
  ticket,
  onUpdateStatus,
  onAssignTicket,
  onSendMessage,
  isSendingMessage = false,
}) => {
  const { user: currentUser } = useAuth();
  const [composerMode, setComposerMode] = useState<'public' | 'internal'>('public');
  const [replyText, setReplyText] = useState('');
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [assigning, setAssigning] = useState(false);

  // AI Copilot State
  const [summary, setSummary] = useState<{
    core_issue: string;
    actions_taken: string[];
    pending_action: string;
  } | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [draftReply, setDraftReply] = useState<string | null>(null);
  const [isDrafting, setIsDrafting] = useState(false);
  const [copilotError, setCopilotError] = useState<string | null>(null);

  // Reset composer and AI state when ticket changes
  useEffect(() => {
    setReplyText('');
    setComposerMode('public');
    setSummary(null);
    setDraftReply(null);
    setCopilotError(null);
  }, [ticket?.id]);

  const handleSummarize = async () => {
    if (!ticket) return;
    setIsSummarizing(true);
    setCopilotError(null);
    try {
      const res = await api.post(`/ai/tickets/${ticket.id}/summarize`);
      setSummary(res.data);
    } catch (err: any) {
      setCopilotError('Failed to summarize thread. Please try again.');
    } finally {
      setIsSummarizing(false);
    }
  };

  const handleSuggestReply = async () => {
    if (!ticket) return;
    setIsDrafting(true);
    setComposerMode('public');
    setCopilotError(null);
    try {
      const res = await api.post(`/ai/tickets/${ticket.id}/suggest-reply`);
      setDraftReply(res.data.reply);
    } catch (err: any) {
      setCopilotError('Failed to generate draft reply. Please try again.');
    } finally {
      setIsDrafting(false);
    }
  };

  const acceptDraft = () => {
    if (draftReply) {
      setReplyText(draftReply);
      setDraftReply(null);
    }
  };

  const editDraft = () => {
    if (draftReply) {
      setReplyText(draftReply);
      setDraftReply(null);
    }
  };

  if (!ticket) {
    return (
      <div className="flex-1 bg-neutral-950 flex items-center justify-center">
        <div className="text-center text-neutral-500">
          <InboxIcon size={48} className="mx-auto mb-4 opacity-40 text-neutral-400" />
          <p className="text-sm font-medium text-neutral-300">Select a conversation to begin</p>
          <p className="text-xs mt-1 text-neutral-500">
            Press <kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-300 border border-neutral-700">Esc</kbd> to deselect
          </p>
        </div>
      </div>
    );
  }

  const handleStatusChange = async (newStatus: TicketStatus) => {
    if (newStatus === ticket.status) return;
    setStatusUpdating(true);
    try {
      await onUpdateStatus(ticket.id, newStatus);
    } finally {
      setStatusUpdating(false);
    }
  };

  const handleAssignToMe = async () => {
    if (!currentUser) return;
    setAssigning(true);
    try {
      await onAssignTicket(ticket.id, Number(currentUser.id));
    } finally {
      setAssigning(false);
    }
  };

  const handleSend = () => {
    if (!replyText.trim() || isSendingMessage) return;
    onSendMessage(ticket.id, replyText, composerMode === 'internal');
    setReplyText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSend();
    }
  };

  const isClosed = ticket.status === 'closed';
  const availableStatuses = ALLOWED_STATUS_OPTIONS[ticket.status] || [ticket.status];
  const isAssignedToMe = currentUser && Number(ticket.assigned_agent_id) === Number(currentUser.id);
  const displayId = ticket.ticket_number || `RSV-${ticket.id}`;
  const messagesList: Message[] = ticket.messages || [];

  return (
    <div className="flex-1 flex bg-neutral-950 overflow-hidden min-w-[500px] text-neutral-100">
      {/* Main Workspace: Header, AI Copilot, Messages, Composer */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-neutral-800">
        {/* Header */}
        <div className="h-16 px-6 border-b border-neutral-800 flex items-center justify-between bg-neutral-900 shrink-0">
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-bold text-neutral-100 line-clamp-1 pr-4">{ticket.subject}</h2>
            <div className="flex items-center gap-3 text-xs text-neutral-400 mt-0.5">
              <span className="font-semibold text-indigo-400">{displayId}</span>
              <span>•</span>
              <span>{ticket.customerName || `Customer #${ticket.customer_id}`}</span>
              <span>•</span>
              <span className="capitalize">{ticket.category}</span>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {/* Assignment control */}
            {ticket.assigned_agent_id ? (
              <span className="text-xs px-2.5 py-1 rounded-md bg-neutral-800 text-neutral-300 border border-neutral-700 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                {isAssignedToMe ? 'Assigned to You' : `Agent #${ticket.assigned_agent_id}`}
              </span>
            ) : (
              <button
                type="button"
                onClick={handleAssignToMe}
                disabled={assigning}
                className="text-xs px-2.5 py-1 rounded-md bg-indigo-950/80 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {assigning ? <Loader2 size={12} className="animate-spin" /> : <UserPlus size={12} />}
                <span>Assign to Me</span>
              </button>
            )}

            {/* Status Dropdown */}
            <div className="relative flex items-center">
              <select
                value={ticket.status}
                disabled={statusUpdating || isClosed}
                onChange={(e) => handleStatusChange(e.target.value as TicketStatus)}
                className="text-xs font-medium border border-neutral-700 rounded-md py-1.5 pl-2.5 pr-6 bg-neutral-800 text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors cursor-pointer disabled:opacity-60"
              >
                {availableStatuses.map((st) => (
                  <option key={st} value={st}>
                    {STATUS_LABELS[st] || st}
                  </option>
                ))}
              </select>
              {statusUpdating && (
                <Loader2 size={12} className="animate-spin text-indigo-400 absolute right-2 pointer-events-none" />
              )}
            </div>

            {/* Quick Close Button */}
            {!isClosed && (
              <button
                type="button"
                onClick={() => handleStatusChange('closed')}
                disabled={statusUpdating}
                className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-medium rounded-md border border-neutral-700 transition-colors shadow-sm disabled:opacity-50"
              >
                Close
              </button>
            )}
          </div>
        </div>

        {/* AI Copilot Action Bar */}
        {!isClosed && (
          <div className="px-6 py-2 bg-gradient-to-r from-purple-950/40 via-indigo-950/30 to-neutral-900 border-b border-neutral-800 flex items-center justify-between shadow-inner shrink-0">
            <div className="flex items-center gap-2 text-purple-300 text-xs font-semibold">
              <Sparkles size={14} className="text-purple-400 animate-pulse" />
              <span>AI Copilot</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSummarize}
                disabled={isSummarizing}
                className="text-xs px-2.5 py-1 bg-neutral-900/80 border border-purple-800/60 text-purple-300 rounded-md font-medium hover:bg-purple-950/60 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1.5"
              >
                {isSummarizing && <Loader2 size={12} className="animate-spin" />}
                <span>{isSummarizing ? 'Summarizing...' : 'Summarize Thread'}</span>
              </button>
              <button
                onClick={handleSuggestReply}
                disabled={isDrafting}
                className="text-xs px-2.5 py-1 bg-purple-600 hover:bg-purple-500 text-white rounded-md font-medium transition-colors shadow-sm disabled:opacity-50 flex items-center gap-1.5"
              >
                {isDrafting && <Loader2 size={12} className="animate-spin" />}
                <span>{isDrafting ? 'Drafting...' : 'Suggest Reply'}</span>
              </button>
            </div>
          </div>
        )}

        {/* Copilot Error Alert */}
        {copilotError && (
          <div className="mx-6 mt-3 p-3 bg-red-950/50 border border-red-800/60 rounded-lg text-xs text-red-300 flex items-center justify-between">
            <span>{copilotError}</span>
            <button onClick={() => setCopilotError(null)} className="text-red-400 hover:text-red-200">
              <X size={14} />
            </button>
          </div>
        )}

        {/* AI Summary Card */}
        {summary && (
          <div className="mx-6 mt-4 p-4 bg-neutral-900 border border-purple-800/60 rounded-xl shadow-lg relative shrink-0">
            <button
              onClick={() => setSummary(null)}
              className="absolute top-3 right-3 text-neutral-400 hover:text-neutral-200"
            >
              <X size={16} />
            </button>
            <h4 className="text-xs font-bold text-purple-300 mb-2.5 flex items-center gap-2 uppercase tracking-wider">
              <Sparkles size={14} className="text-purple-400" />
              Conversation Summary
            </h4>
            <div className="space-y-2.5 text-xs">
              <div>
                <span className="font-semibold text-neutral-300 block mb-0.5">Core Issue:</span>
                <p className="text-neutral-400">{summary.core_issue}</p>
              </div>
              {summary.actions_taken?.length > 0 && (
                <div>
                  <span className="font-semibold text-neutral-300 block mb-0.5">Actions Taken:</span>
                  <ul className="list-disc pl-4 text-neutral-400 space-y-0.5">
                    {summary.actions_taken.map((action, i) => (
                      <li key={i}>{action}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <span className="font-semibold text-neutral-300 block mb-0.5">Pending Action:</span>
                <p className="text-purple-200 font-medium">{summary.pending_action}</p>
              </div>
            </div>
          </div>
        )}

        {/* AI Draft Card */}
        {draftReply && (
          <div className="mx-6 mt-4 p-4 bg-gradient-to-br from-indigo-950/60 to-purple-950/60 border border-purple-800/60 rounded-xl shadow-lg relative shrink-0">
            <button
              onClick={() => setDraftReply(null)}
              className="absolute top-3 right-3 text-neutral-400 hover:text-neutral-200"
            >
              <X size={16} />
            </button>
            <h4 className="text-xs font-bold text-purple-300 mb-2 flex items-center gap-2 uppercase tracking-wider">
              <Sparkles size={14} className="text-purple-400" />
              AI Suggested Reply
            </h4>
            <p className="text-xs text-neutral-200 whitespace-pre-wrap mb-3.5 bg-neutral-900/80 p-3 rounded-lg border border-purple-900/60 font-sans leading-relaxed">
              {draftReply}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={acceptDraft}
                className="text-xs px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-md font-semibold transition-colors shadow-sm"
              >
                Insert into Composer
              </button>
              <button
                onClick={editDraft}
                className="text-xs px-3 py-1.5 bg-neutral-900 border border-purple-800 text-purple-300 rounded-md font-medium hover:bg-neutral-800 transition-colors shadow-sm"
              >
                Edit Draft
              </button>
              <button
                onClick={handleSuggestReply}
                disabled={isDrafting}
                className="text-xs px-3 py-1.5 bg-neutral-900 border border-neutral-700 text-neutral-400 rounded-md font-medium hover:bg-neutral-800 transition-colors shadow-sm ml-auto"
              >
                Regenerate
              </button>
            </div>
          </div>
        )}

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 bg-neutral-950">
          {/* Initial Ticket Description as first entry */}
          {ticket.description && (
            <div className="flex gap-3">
              <div className="shrink-0 w-8 h-8 rounded-full bg-neutral-800 text-neutral-300 flex items-center justify-center font-bold text-xs border border-neutral-700">
                {ticket.customerName?.charAt(0) || 'C'}
              </div>
              <div className="flex-1 max-w-[85%]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold text-neutral-200">
                    {ticket.customerName || `Customer #${ticket.customer_id}`}
                  </span>
                  <span className="text-[10px] text-neutral-500">Initial Request</span>
                </div>
                <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-neutral-900 text-neutral-200 border border-neutral-800 shadow-sm text-xs leading-relaxed whitespace-pre-wrap">
                  {ticket.description}
                </div>
              </div>
            </div>
          )}

          {/* Thread Messages */}
          {messagesList.map((msg) => {
            const isInternal = Boolean(msg.is_internal || msg.isInternal);

            if (isInternal) {
              return (
                <div key={msg.id} className="flex gap-3">
                  <div className="shrink-0 w-8 h-8 rounded-full bg-amber-950/80 text-amber-400 flex items-center justify-center border border-amber-800/80">
                    <Lock size={14} />
                  </div>
                  <div className="flex-1 max-w-[85%]">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold text-amber-300">
                        {typeof msg.sender === 'object' ? msg.sender.full_name : msg.agentName || 'Agent'}
                      </span>
                      <span className="text-[10px] font-bold text-amber-400 px-1.5 py-0.2 rounded bg-amber-950 border border-amber-800/60">
                        Internal Note
                      </span>
                      <span className="text-[10px] text-neutral-500">
                        {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : msg.timestamp}
                      </span>
                    </div>
                    <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-amber-950/30 text-amber-100 border border-amber-800/50 shadow-sm text-xs leading-relaxed whitespace-pre-wrap">
                      {msg.body || msg.text}
                    </div>
                  </div>
                </div>
              );
            }

            const senderRole = typeof msg.sender === 'object' ? msg.sender.role : msg.sender;
            const isCustomer = senderRole === 'customer' || senderRole === 'CUSTOMER';
            const senderName =
              typeof msg.sender === 'object'
                ? msg.sender.full_name
                : isCustomer
                ? ticket.customerName || 'Customer'
                : msg.agentName || 'Support Agent';

            return (
              <div key={msg.id} className="flex gap-3">
                <div
                  className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs border ${
                    isCustomer
                      ? 'bg-neutral-800 text-neutral-200 border-neutral-700'
                      : 'bg-indigo-900 text-indigo-200 border-indigo-700'
                  }`}
                >
                  {senderName.charAt(0)}
                </div>
                <div className="flex-1 max-w-[85%]">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-neutral-200">{senderName}</span>
                    <span className="text-[10px] text-neutral-500">
                      {msg.created_at
                        ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        : msg.timestamp}
                    </span>
                  </div>
                  <div
                    className={`px-4 py-3 rounded-2xl rounded-tl-sm text-xs leading-relaxed shadow-sm border whitespace-pre-wrap ${
                      isCustomer
                        ? 'bg-neutral-900 text-neutral-200 border-neutral-800'
                        : 'bg-indigo-950/40 text-indigo-100 border-indigo-900/60'
                    }`}
                  >
                    {msg.body || msg.text}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Composer */}
        <div className="p-4 bg-neutral-900 border-t border-neutral-800 shrink-0">
          {isClosed ? (
            <div className="text-center py-3 text-neutral-500 text-xs bg-neutral-950 rounded-lg border border-neutral-800">
              This ticket is closed. Re-open or change status to reply.
            </div>
          ) : (
            <div className="flex flex-col border border-neutral-800 rounded-xl overflow-hidden focus-within:ring-1 focus-within:ring-indigo-500 focus-within:border-indigo-500 bg-neutral-950 transition-shadow">
              {/* Tabs */}
              <div className="flex border-b border-neutral-800 bg-neutral-900">
                <button
                  type="button"
                  onClick={() => setComposerMode('public')}
                  className={`px-4 py-2 text-xs font-medium transition-colors ${
                    composerMode === 'public'
                      ? 'text-white bg-neutral-950 border-r border-neutral-800 font-semibold'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  Public Reply
                </button>
                <button
                  type="button"
                  onClick={() => setComposerMode('internal')}
                  className={`px-4 py-2 text-xs font-medium flex items-center gap-1.5 transition-colors ${
                    composerMode === 'internal'
                      ? 'text-amber-300 bg-amber-950/40 border-r border-amber-900/60 font-semibold'
                      : 'text-neutral-400 hover:text-amber-300'
                  }`}
                >
                  <Lock size={12} />
                  <span>Internal Note</span>
                </button>
              </div>

              <div className={`p-3 ${composerMode === 'internal' ? 'bg-amber-950/10' : 'bg-neutral-950'}`}>
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    composerMode === 'internal'
                      ? 'Write a private note (only visible to team members)...'
                      : 'Write a solution-oriented reply to the customer...'
                  }
                  rows={3}
                  className="w-full bg-transparent outline-none resize-none text-xs text-neutral-100 placeholder-neutral-500 min-h-[70px] leading-relaxed"
                />
                <div className="flex justify-between items-center mt-2 pt-2 border-t border-neutral-800/80">
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wider">
                    Press <kbd className="text-neutral-400">Ctrl + Enter</kbd> to send
                  </span>
                  <button
                    type="button"
                    onClick={handleSend}
                    disabled={!replyText.trim() || isSendingMessage}
                    className={`px-4 py-1.5 rounded-lg text-xs font-semibold text-white transition-all disabled:opacity-50 flex items-center gap-1.5 cursor-pointer ${
                      composerMode === 'internal'
                        ? 'bg-amber-700 hover:bg-amber-600 shadow-sm shadow-amber-900/40'
                        : 'bg-indigo-600 hover:bg-indigo-500 shadow-sm shadow-indigo-600/30'
                    }`}
                  >
                    {isSendingMessage ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <Send size={13} />
                    )}
                    <span>{composerMode === 'internal' ? 'Post Note' : 'Send Reply'}</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Customer 360 Sidebar */}
      <div className="w-64 bg-neutral-900/80 p-5 overflow-y-auto hidden lg:block shrink-0 border-l border-neutral-800/60">
        <h3 className="text-xs font-bold text-neutral-400 uppercase tracking-wider mb-4">Customer 360</h3>

        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-full bg-neutral-800 border border-neutral-700 flex items-center justify-center text-lg font-bold text-neutral-200 mb-2.5">
            {ticket.customerName?.charAt(0) || 'C'}
          </div>
          <h4 className="font-semibold text-sm text-neutral-100">{ticket.customerName || `Customer #${ticket.customer_id}`}</h4>
          <p className="text-xs text-neutral-400 truncate w-full">{ticket.customerEmail || 'Verified Customer'}</p>
        </div>

        <div className="space-y-4 text-xs">
          <div className="p-3 bg-neutral-950 rounded-lg border border-neutral-800">
            <span className="block text-[11px] text-neutral-400 mb-1">Subscription Plan</span>
            <span className="inline-block px-2 py-0.5 bg-indigo-950 text-indigo-300 text-[10px] font-bold rounded border border-indigo-800">
              {ticket.customerPlan || 'Enterprise Plan'}
            </span>
          </div>

          <div className="p-3 bg-neutral-950 rounded-lg border border-neutral-800 space-y-2">
            <span className="block text-[11px] text-neutral-400 font-semibold uppercase tracking-wider">SLA Target</span>
            <div className="flex justify-between items-center text-neutral-300">
              <span>Priority Tier:</span>
              <span className="font-semibold capitalize text-indigo-300">{ticket.priority}</span>
            </div>
            {ticket.first_response_due_at && (
              <div className="flex justify-between items-center text-neutral-400 text-[11px]">
                <span>Response Due:</span>
                <span>{new Date(ticket.first_response_due_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
            )}
            {ticket.sla_first_response_breached && (
              <div className="text-[10px] text-red-400 font-semibold bg-red-950/60 p-1.5 rounded border border-red-800/60">
                First Response SLA Breached
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
