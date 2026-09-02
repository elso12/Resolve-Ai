import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Loader2, Sparkles, ChevronRight, X } from 'lucide-react';
import api from '../../services/api';

export const NewTicketPage: React.FC = () => {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    subject: '',
    category: 'GENERAL',
    priority: 'MEDIUM',
    description: '',
  });

  // AI Deflection / Quick Suggestion State
  const [isCheckingAi, setIsCheckingAi] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<{ answer: string; sources: Array<{ id: number; title: string; snippet: string }> } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleCheckInstantSolution = async () => {
    if (!formData.subject.trim()) return;
    setIsCheckingAi(true);
    try {
      const res = await api.post('/knowledge/ask', {
        question: `${formData.subject}: ${formData.description}`.trim(),
      });
      if (res.data && !res.data.answer.includes('cannot find this in our knowledge base')) {
        setAiSuggestion(res.data);
      } else {
        setAiSuggestion(null);
      }
    } catch {
      setAiSuggestion(null);
    } finally {
      setIsCheckingAi(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const res = await api.post('/tickets', {
        subject: formData.subject.trim(),
        description: formData.description.trim(),
        category: formData.category.toLowerCase(),
        priority: formData.priority.toLowerCase(),
      });
      const createdTicket = res.data;
      navigate(`/help/tickets/${createdTicket.id || createdTicket.ticket_number}`, {
        state: { showSuccess: true },
      });
    } catch (err: any) {
      console.error('Failed to create ticket:', err);
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || d).join(', ')
          : 'Failed to create ticket. Please check your inputs and try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const maxDescLength = 2000;
  const charsRemaining = maxDescLength - formData.description.length;

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-neutral-900 mb-2">Submit a request</h1>
        <p className="text-neutral-600">
          Please provide as much detail as possible so we can best assist you.
        </p>
      </div>

      {/* AI Instant Solution Deflection Card */}
      {aiSuggestion && (
        <div className="mb-6 p-5 bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-200 rounded-xl shadow-sm relative animate-in fade-in slide-in-from-top-2 duration-300">
          <button
            onClick={() => setAiSuggestion(null)}
            className="absolute top-3 right-3 text-neutral-400 hover:text-neutral-600"
            aria-label="Dismiss suggestion"
          >
            <X size={16} />
          </button>
          <div className="flex items-center gap-2 text-xs font-bold text-purple-800 uppercase tracking-wider mb-2">
            <Sparkles size={14} className="text-purple-600" />
            Instant AI Knowledge Solution
          </div>
          <p className="text-sm text-neutral-800 leading-relaxed whitespace-pre-wrap mb-3">
            {aiSuggestion.answer}
          </p>
          {aiSuggestion.sources.length > 0 && (
            <div className="text-xs text-neutral-600 pt-2 border-t border-purple-200/60 flex items-center justify-between">
              <span>Grounded in: <strong>{aiSuggestion.sources[0].title}</strong></span>
              <button
                type="button"
                onClick={() => navigate('/help')}
                className="text-purple-700 hover:text-purple-900 font-semibold inline-flex items-center gap-1"
              >
                View Article <ChevronRight size={12} />
              </button>
            </div>
          )}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-white p-6 md:p-8 rounded-xl shadow-soft border border-neutral-200"
      >
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-800 text-sm rounded-lg flex items-center gap-2">
            <AlertCircle size={18} className="text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        <div className="space-y-6">
          {/* Subject */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="subject" className="block text-sm font-medium text-neutral-900">
                Subject
              </label>
              {formData.subject.length >= 4 && !aiSuggestion && (
                <button
                  type="button"
                  onClick={handleCheckInstantSolution}
                  disabled={isCheckingAi}
                  className="text-xs text-purple-600 hover:text-purple-800 font-semibold flex items-center gap-1 transition-colors"
                >
                  <Sparkles size={12} />
                  {isCheckingAi ? 'Finding solutions...' : 'Check instant answer'}
                </button>
              )}
            </div>
            <input
              type="text"
              id="subject"
              name="subject"
              required
              value={formData.subject}
              onChange={handleInputChange}
              className="w-full px-4 py-2 border border-neutral-300 rounded-md focus:ring-2 focus:ring-neutral-900 focus:border-transparent outline-none transition-all"
              placeholder="Brief description of the issue"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Category */}
            <div>
              <label htmlFor="category" className="block text-sm font-medium text-neutral-900 mb-1">
                Category
              </label>
              <select
                id="category"
                name="category"
                value={formData.category}
                onChange={handleInputChange}
                className="w-full px-4 py-2 border border-neutral-300 rounded-md focus:ring-2 focus:ring-neutral-900 focus:border-transparent outline-none bg-white transition-all"
              >
                <option value="GENERAL">General Inquiry</option>
                <option value="TECHNICAL">Technical Support</option>
                <option value="BILLING">Billing Question</option>
                <option value="ACCOUNT">Account Issue</option>
              </select>
            </div>

            {/* Priority */}
            <div>
              <label htmlFor="priority" className="block text-sm font-medium text-neutral-900 mb-1">
                Priority
              </label>
              <select
                id="priority"
                name="priority"
                value={formData.priority}
                onChange={handleInputChange}
                className="w-full px-4 py-2 border border-neutral-300 rounded-md focus:ring-2 focus:ring-neutral-900 focus:border-transparent outline-none bg-white transition-all"
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium (Normal)</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical / Urgent</option>
              </select>
            </div>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-neutral-900 mb-1">
              Description
            </label>
            <textarea
              id="description"
              name="description"
              required
              maxLength={maxDescLength}
              rows={6}
              value={formData.description}
              onChange={handleInputChange}
              className="w-full px-4 py-2 border border-neutral-300 rounded-md focus:ring-2 focus:ring-neutral-900 focus:border-transparent outline-none resize-y transition-all"
              placeholder="Please describe the issue in detail..."
            ></textarea>
            <div className="mt-1 flex justify-between items-center text-xs text-neutral-500">
              <span>Markdown is supported</span>
              <span className={charsRemaining < 100 ? 'text-red-500 font-medium' : ''}>
                {charsRemaining} characters remaining
              </span>
            </div>
          </div>
        </div>

        <div className="mt-8 flex items-center justify-end gap-4">
          <button
            type="button"
            onClick={() => navigate('/help/tickets')}
            className="px-4 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-900 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !formData.subject || !formData.description}
            className="flex items-center justify-center gap-2 px-6 py-2 bg-primary hover:bg-primary-hover text-white rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Submitting...
              </>
            ) : (
              'Submit Request'
            )}
          </button>
        </div>
      </form>

      <div className="mt-6 flex items-start gap-3 p-4 bg-blue-50 text-blue-800 rounded-md">
        <AlertCircle size={20} className="shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-medium">Need immediate assistance?</p>
          <p className="mt-1 text-blue-700">
            Check out our Knowledge Base first—many common questions are answered there instantly.
          </p>
        </div>
      </div>
    </div>
  );
};
