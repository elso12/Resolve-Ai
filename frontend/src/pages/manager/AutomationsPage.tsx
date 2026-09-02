import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Filter,
  Plus,
  Power,
  RefreshCw,
  Trash2,
  Workflow,
  Zap,
} from 'lucide-react';
import api from '../../services/api';

interface AutomationRule {
  id: number;
  name: string;
  is_active: boolean;
  event_trigger: string;
  conditions: Record<string, any>;
  actions: Record<string, any>;
  created_at: string;
}

export const AutomationsPage: React.FC = () => {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState('');
  const [eventTrigger, setEventTrigger] = useState('TICKET_CREATED');
  const [conditionCategory, setConditionCategory] = useState('billing');
  const [conditionPriority, setConditionPriority] = useState('');
  const [conditionKeyword, setConditionKeyword] = useState('');
  const [actionPriority, setActionPriority] = useState('high');
  const [actionStatus, setActionStatus] = useState('');
  const [actionNote, setActionNote] = useState('Automated priority elevation applied via workflow rule.');

  useEffect(() => {
    fetchRules();
  }, []);

  const fetchRules = async () => {
    setIsRefreshing(true);
    try {
      const res = await api.get('/automations');
      setRules(res.data);
    } catch (err: any) {
      console.error('Failed to load automation rules:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  const handleToggleActive = async (rule: AutomationRule) => {
    try {
      const res = await api.patch(`/automations/${rule.id}`, {
        is_active: !rule.is_active,
      });
      setRules((prev) => prev.map((r) => (r.id === rule.id ? res.data : r)));
    } catch (err) {
      console.error('Failed to toggle rule active state:', err);
    }
  };

  const handleDeleteRule = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this automation rule?')) return;
    try {
      await api.delete(`/automations/${id}`);
      setRules((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      console.error('Failed to delete rule:', err);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg('Please enter a descriptive rule name.');
      return;
    }

    const conditions: Record<string, any> = {};
    if (conditionCategory) conditions.category = conditionCategory;
    if (conditionPriority) conditions.priority = conditionPriority;
    if (conditionKeyword) conditions.subject_contains = conditionKeyword;

    const actions: Record<string, any> = {};
    if (actionPriority) actions.set_priority = actionPriority;
    if (actionStatus) actions.set_status = actionStatus;
    if (actionNote) actions.add_internal_note = actionNote;

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await api.post('/automations', {
        name: name.trim(),
        event_trigger: eventTrigger,
        conditions,
        actions,
        is_active: true,
      });
      setRules((prev) => [res.data, ...prev]);
      setShowCreateModal(false);
      // Reset form
      setName('');
      setConditionKeyword('');
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to create automation rule.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto text-neutral-100">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-800 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Workflow className="text-purple-400" size={26} />
              Workflow Automations (ECA Engine)
            </h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <Zap size={12} /> Active Rules: {rules.filter((r) => r.is_active).length}
            </span>
          </div>
          <p className="text-xs text-neutral-400 mt-1">
            Build event-driven rules: WHEN [Event] AND [Condition] THEN [Action] to route, escalate, and audit tickets automatically.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchRules}
            disabled={isRefreshing}
            className="p-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-neutral-300 hover:text-white rounded-lg transition-colors shadow-sm disabled:opacity-50"
            title="Refresh rules"
          >
            <RefreshCw size={16} className={isRefreshing ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg shadow-md hover:shadow-purple-600/20 transition-all"
          >
            <Plus size={16} />
            Create Rule
          </button>
        </div>
      </div>

      {/* Rules List */}
      {isLoading ? (
        <div className="flex items-center justify-center p-12 text-neutral-400">
          <RefreshCw className="animate-spin text-purple-500 mr-2" size={24} />
          <span className="text-sm font-medium">Loading automation rules...</span>
        </div>
      ) : rules.length === 0 ? (
        <div className="bg-neutral-800/30 border border-neutral-800 rounded-2xl p-12 text-center max-w-lg mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-purple-500/10 text-purple-400 flex items-center justify-center mx-auto mb-4 border border-purple-500/20">
            <Workflow size={28} />
          </div>
          <h3 className="text-base font-semibold text-white">No Automation Rules Configured</h3>
          <p className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
            Create automated workflows to triage urgent requests, route VIP accounts, or escalate SLA breaches autonomously.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition-all shadow-md"
          >
            <Plus size={16} />
            Create Your First Rule
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`border rounded-xl p-5 transition-all backdrop-blur-sm relative overflow-hidden ${
                rule.is_active
                  ? 'bg-neutral-800/60 border-neutral-700/80 shadow-sm hover:border-purple-500/40'
                  : 'bg-neutral-900/40 border-neutral-800/60 opacity-60'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                {/* Rule Title & Trigger */}
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      {rule.name}
                    </h3>
                    <span
                      className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                        rule.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-neutral-800 text-neutral-400 border-neutral-700'
                      }`}
                    >
                      {rule.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-neutral-400">
                    <span className="text-purple-400 font-semibold font-mono">WHEN</span>
                    <span className="px-2 py-0.5 rounded bg-neutral-900 border border-neutral-750 text-neutral-300 font-mono text-[11px]">
                      {rule.event_trigger}
                    </span>
                  </div>
                </div>

                {/* Actions & Toggles */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggleActive(rule)}
                    className={`p-2 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5 ${
                      rule.is_active
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
                        : 'bg-neutral-800 text-neutral-400 border-neutral-700 hover:text-white'
                    }`}
                    title={rule.is_active ? 'Disable rule' : 'Enable rule'}
                  >
                    <Power size={14} />
                    {rule.is_active ? 'Enabled' : 'Disabled'}
                  </button>
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    className="p-2 text-neutral-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors border border-transparent hover:border-red-500/20"
                    title="Delete rule"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              {/* ECA Statement Breakdown */}
              <div className="mt-4 pt-4 border-t border-neutral-800/80 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                {/* AND (Conditions) */}
                <div className="bg-neutral-900/80 p-3 rounded-lg border border-neutral-800">
                  <div className="text-neutral-400 font-semibold flex items-center gap-1.5 mb-2">
                    <Filter size={13} className="text-purple-400" />
                    <span>AND Conditions:</span>
                  </div>
                  <div className="space-y-1 text-neutral-300 font-mono text-[11px]">
                    {Object.keys(rule.conditions || {}).length === 0 ? (
                      <span className="text-neutral-500 italic">Always matches (All tickets)</span>
                    ) : (
                      Object.entries(rule.conditions).map(([k, v]) => (
                        <div key={k} className="flex items-center gap-1.5">
                          <span className="text-purple-300">{k}</span>
                          <span className="text-neutral-500">==</span>
                          <span className="text-amber-300 font-semibold">"{String(v)}"</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* THEN (Actions) */}
                <div className="bg-neutral-900/80 p-3 rounded-lg border border-neutral-800">
                  <div className="text-neutral-400 font-semibold flex items-center gap-1.5 mb-2">
                    <ArrowRight size={13} className="text-emerald-400" />
                    <span>THEN Actions:</span>
                  </div>
                  <div className="space-y-1 text-neutral-300 font-mono text-[11px]">
                    {Object.keys(rule.actions || {}).length === 0 ? (
                      <span className="text-neutral-500 italic">No actions defined</span>
                    ) : (
                      Object.entries(rule.actions).map(([k, v]) => (
                        <div key={k} className="flex items-center gap-1.5">
                          <span className="text-emerald-400">{k}:</span>
                          <span className="text-neutral-200 font-semibold">"{String(v)}"</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Rule Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-6 relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-purple-600/20 text-purple-400 border border-purple-500/30">
                  <Workflow size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Create Automation Rule</h3>
                  <p className="text-xs text-neutral-400">Define automated ECA workflow logic.</p>
                </div>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-neutral-400 hover:text-white text-lg font-bold p-1"
              >
                ✕
              </button>
            </div>

            {errorMsg && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-xs flex items-center gap-2">
                <AlertCircle size={16} />
                <span>{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleCreateRule} className="space-y-4 text-xs">
              {/* Rule Name */}
              <div>
                <label className="block text-neutral-300 font-medium mb-1">Rule Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Elevate Billing Inquiries to High"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500 text-xs"
                />
              </div>

              {/* WHEN: Event Trigger */}
              <div>
                <label className="block text-purple-300 font-semibold mb-1 uppercase tracking-wider text-[11px]">
                  WHEN (Trigger Event)
                </label>
                <select
                  value={eventTrigger}
                  onChange={(e) => setEventTrigger(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500 text-xs"
                >
                  <option value="TICKET_CREATED">Ticket Created (TICKET_CREATED)</option>
                  <option value="TICKET_STATUS_CHANGED">Ticket Status Changed (TICKET_STATUS_CHANGED)</option>
                  <option value="SLA_BREACHED">SLA Deadline Breached (SLA_BREACHED)</option>
                </select>
              </div>

              {/* AND: Conditions */}
              <div className="p-3.5 bg-neutral-950/60 border border-neutral-800 rounded-xl space-y-3">
                <span className="block text-neutral-300 font-semibold text-[11px] uppercase tracking-wider">
                  AND (Conditions)
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-neutral-400 text-[11px] mb-1">Category Matches</label>
                    <select
                      value={conditionCategory}
                      onChange={(e) => setConditionCategory(e.target.value)}
                      className="w-full bg-neutral-900 border border-neutral-750 rounded-lg px-2.5 py-1.5 text-white text-xs"
                    >
                      <option value="">Any Category</option>
                      <option value="billing">Billing</option>
                      <option value="technical">Technical</option>
                      <option value="account">Account</option>
                      <option value="general">General</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-neutral-400 text-[11px] mb-1">Current Priority Matches</label>
                    <select
                      value={conditionPriority}
                      onChange={(e) => setConditionPriority(e.target.value)}
                      className="w-full bg-neutral-900 border border-neutral-750 rounded-lg px-2.5 py-1.5 text-white text-xs"
                    >
                      <option value="">Any Priority</option>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-neutral-400 text-[11px] mb-1">Subject Keyword (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. invoice, refund, urgent"
                    value={conditionKeyword}
                    onChange={(e) => setConditionKeyword(e.target.value)}
                    className="w-full bg-neutral-900 border border-neutral-750 rounded-lg px-2.5 py-1.5 text-white text-xs"
                  />
                </div>
              </div>

              {/* THEN: Actions */}
              <div className="p-3.5 bg-neutral-950/60 border border-neutral-800 rounded-xl space-y-3">
                <span className="block text-emerald-400 font-semibold text-[11px] uppercase tracking-wider">
                  THEN (Execute Actions)
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-neutral-400 text-[11px] mb-1">Set Ticket Priority</label>
                    <select
                      value={actionPriority}
                      onChange={(e) => setActionPriority(e.target.value)}
                      className="w-full bg-neutral-900 border border-neutral-750 rounded-lg px-2.5 py-1.5 text-white text-xs"
                    >
                      <option value="">No change</option>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-neutral-400 text-[11px] mb-1">Set Ticket Status</label>
                    <select
                      value={actionStatus}
                      onChange={(e) => setActionStatus(e.target.value)}
                      className="w-full bg-neutral-900 border border-neutral-750 rounded-lg px-2.5 py-1.5 text-white text-xs"
                    >
                      <option value="">No change</option>
                      <option value="in_progress">In Progress</option>
                      <option value="waiting_on_customer">Waiting on Customer</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-neutral-400 text-[11px] mb-1">Add Internal Audit Note</label>
                  <input
                    type="text"
                    placeholder="e.g. Auto-routed via Billing Priority rule."
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                    className="w-full bg-neutral-900 border border-neutral-750 rounded-lg px-2.5 py-1.5 text-white text-xs"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-neutral-800">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white transition-colors text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-semibold transition-all shadow-md text-xs disabled:opacity-50 flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" /> Saving...
                    </>
                  ) : (
                    'Create Rule'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
