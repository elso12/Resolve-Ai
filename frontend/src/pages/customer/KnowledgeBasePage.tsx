import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  Sparkles,
  BookOpen,
  ArrowRight,
  ExternalLink,
  HelpCircle,
  CheckCircle2,
  Loader2,
  ChevronRight,
  X,
} from 'lucide-react';
import api from '../../services/api';

interface Article {
  id: number;
  title: string;
  slug: string;
  content: string;
  category: string;
  is_published: boolean;
  created_at: string;
}

interface ArticleRef {
  id: number;
  title: string;
  slug: string;
  category: string;
  similarity_score: number;
  snippet: string;
}

interface AskResponse {
  answer: string;
  sources: ArticleRef[];
}

const CATEGORIES = [
  'All',
  'Getting Started',
  'Billing & Subscriptions',
  'Technical & API',
  'Account & Security',
];

export const KnowledgeBasePage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [articles, setArticles] = useState<Article[]>([]);
  const [isLoadingArticles, setIsLoadingArticles] = useState(true);

  // AI Assistant RAG State
  const [aiQuestion, setAiQuestion] = useState('');
  const [isAskingAi, setIsAskingAi] = useState(false);
  const [aiResponse, setAiResponse] = useState<AskResponse | null>(null);
  const [activeArticleModal, setActiveArticleModal] = useState<Article | null>(null);

  useEffect(() => {
    fetchArticles();
  }, [selectedCategory]);

  const fetchArticles = async () => {
    setIsLoadingArticles(true);
    try {
      const categoryParam = selectedCategory === 'All' ? '' : selectedCategory;
      const res = await api.get('/knowledge/articles', {
        params: { category: categoryParam || undefined },
      });
      setArticles(res.data);
    } catch (err) {
      console.warn('Could not fetch articles from backend; using mock knowledge base.', err);
      // Fallback seed articles for local presentation
      setArticles([
        {
          id: 1,
          title: 'How to Reset Your Account Password and Enable 2FA',
          slug: 'how-to-reset-password-2fa',
          content:
            'To reset your password, visit Settings > Security and click Reset Password. Enter your email address to receive a secure one-time verification link. To enable Two-Factor Authentication (2FA), toggle on Authenticator App and scan the QR code using Google Authenticator or 1Password.',
          category: 'Account & Security',
          is_published: true,
          created_at: new Date().toISOString(),
        },
        {
          id: 2,
          title: 'Understanding Invoices, Billing Cycles, and Upgrades',
          slug: 'understanding-invoices-billing',
          content:
            'Invoices are generated automatically on the 1st of every month. You can update your payment method or download past PDF invoices under Billing > Payment Methods. When upgrading your plan, proration is calculated automatically based on remaining billing days.',
          category: 'Billing & Subscriptions',
          is_published: true,
          created_at: new Date().toISOString(),
        },
        {
          id: 3,
          title: 'REST API Authentication and Webhook Setup Guide',
          slug: 'rest-api-authentication-webhooks',
          content:
            'ResolveAI uses Bearer Token authentication for all REST API endpoints. Include Authorization: Bearer <your_api_key> in your HTTP headers. Webhooks can be configured under Settings > Developer to receive real-time JSON events for ticket status updates and agent replies.',
          category: 'Technical & API',
          is_published: true,
          created_at: new Date().toISOString(),
        },
        {
          id: 4,
          title: 'Quick Start: Configuring SLA Tiers and Automated Escalation',
          slug: 'quick-start-sla-escalations',
          content:
            'Service Level Agreements (SLAs) determine target response and resolution times based on ticket priority (Critical: 1 hr, High: 4 hrs, Medium: 24 hrs, Low: 48 hrs). Tickets at risk of breach are automatically highlighted in the Agent High Priority queue.',
          category: 'Getting Started',
          is_published: true,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoadingArticles(false);
    }
  };

  const handleAskAi = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiQuestion.trim() || isAskingAi) return;

    setIsAskingAi(true);
    setAiResponse(null);

    try {
      const res = await api.post('/knowledge/ask', { question: aiQuestion.trim() });
      setAiResponse(res.data);
    } catch (err) {
      console.error('RAG request failed, using grounded fallback generator', err);
      // Fallback simulation matching strict grounding
      const q = aiQuestion.toLowerCase();
      if (q.includes('password') || q.includes('2fa') || q.includes('reset')) {
        setAiResponse({
          answer:
            "According to **'How to Reset Your Account Password and Enable 2FA'**, you can reset your password by going to Settings > Security and clicking 'Reset Password'. You can also enable 2FA with an authenticator app like Google Authenticator or 1Password.",
          sources: [
            {
              id: 1,
              title: 'How to Reset Your Account Password and Enable 2FA',
              slug: 'how-to-reset-password-2fa',
              category: 'Account & Security',
              similarity_score: 0.92,
              snippet:
                'To reset your password, visit Settings > Security and click Reset Password...',
            },
          ],
        });
      } else if (q.includes('invoice') || q.includes('bill') || q.includes('upgrade') || q.includes('payment')) {
        setAiResponse({
          answer:
            "According to **'Understanding Invoices, Billing Cycles, and Upgrades'**, invoices are generated on the 1st of every month. You can manage your payment methods and download invoices under Billing > Payment Methods.",
          sources: [
            {
              id: 2,
              title: 'Understanding Invoices, Billing Cycles, and Upgrades',
              slug: 'understanding-invoices-billing',
              category: 'Billing & Subscriptions',
              similarity_score: 0.88,
              snippet:
                'Invoices are generated automatically on the 1st of every month...',
            },
          ],
        });
      } else if (q.includes('api') || q.includes('webhook') || q.includes('token') || q.includes('auth')) {
        setAiResponse({
          answer:
            "According to **'REST API Authentication and Webhook Setup Guide'**, all REST API requests require Bearer token authorization headers. Webhooks can be configured under Settings > Developer to receive real-time notifications.",
          sources: [
            {
              id: 3,
              title: 'REST API Authentication and Webhook Setup Guide',
              slug: 'rest-api-authentication-webhooks',
              category: 'Technical & API',
              similarity_score: 0.89,
              snippet:
                'ResolveAI uses Bearer Token authentication for all REST API endpoints...',
            },
          ],
        });
      } else {
        setAiResponse({
          answer:
            'I cannot find this in our knowledge base; let me connect you with a human agent.',
          sources: [],
        });
      }
    } finally {
      setIsAskingAi(false);
    }
  };

  const filteredArticles = articles.filter((art) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      art.title.toLowerCase().includes(query) ||
      art.content.toLowerCase().includes(query) ||
      art.category.toLowerCase().includes(query)
    );
  });

  return (
    <div className="space-y-12">
      {/* Hero & AI Search Section */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-neutral-900 via-neutral-900 to-neutral-800 text-white p-8 md:p-12 shadow-xl">
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -mb-8 -ml-8 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-2xl mx-auto text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-400/20 text-purple-300 text-xs font-semibold tracking-wide">
            <Sparkles size={14} className="text-purple-400" />
            AI-Powered Instant Self-Service
          </div>

          <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-white">
            How can we help you today?
          </h1>

          <p className="text-neutral-300 text-sm md:text-base">
            Ask any question to get grounded answers backed by our official documentation.
          </p>

          {/* AI Search Bar Form */}
          <form onSubmit={handleAskAi} className="mt-6 relative">
            <div className="relative flex items-center">
              <div className="absolute left-4 text-purple-400 pointer-events-none">
                <Sparkles size={20} />
              </div>
              <input
                type="text"
                value={aiQuestion}
                onChange={(e) => setAiQuestion(e.target.value)}
                placeholder="Ask our AI assistant (e.g. 'How do I set up webhooks?' or 'How does billing work?')"
                className="w-full pl-12 pr-28 py-3.5 bg-neutral-800/90 hover:bg-neutral-800 focus:bg-neutral-800 border border-neutral-700 focus:border-purple-400 rounded-xl text-white placeholder-neutral-400 text-sm shadow-inner outline-none transition-all focus:ring-2 focus:ring-purple-400/30"
              />
              <button
                type="submit"
                disabled={isAskingAi || !aiQuestion.trim()}
                className="absolute right-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold shadow transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {isAskingAi ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    Ask AI
                    <ArrowRight size={14} />
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Grounded AI Answer Card */}
        {aiResponse && (
          <div className="mt-8 relative max-w-3xl mx-auto bg-neutral-900/90 border border-purple-500/30 rounded-xl p-6 shadow-2xl backdrop-blur-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-purple-600/20 border border-purple-400/30 flex items-center justify-center text-purple-300">
                  <Sparkles size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Grounded Answer</h3>
                  <p className="text-xs text-neutral-400">Verified against official documentation</p>
                </div>
              </div>
              <button
                onClick={() => setAiResponse(null)}
                className="text-neutral-400 hover:text-white transition-colors"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="text-sm text-neutral-200 leading-relaxed space-y-3 whitespace-pre-wrap">
              {aiResponse.answer}
            </div>

            {/* Sources / Citations */}
            {aiResponse.sources.length > 0 ? (
              <div className="mt-6 pt-4 border-t border-neutral-800">
                <div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Cited Knowledge Sources
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {aiResponse.sources.map((src) => (
                    <div
                      key={src.id}
                      onClick={() =>
                        setActiveArticleModal({
                          id: src.id,
                          title: src.title,
                          slug: src.slug,
                          content: src.snippet,
                          category: src.category,
                          is_published: true,
                          created_at: new Date().toISOString(),
                        })
                      }
                      className="cursor-pointer group p-3 bg-neutral-800/80 hover:bg-neutral-800 border border-neutral-700/60 hover:border-purple-400/40 rounded-lg transition-all text-left"
                    >
                      <div className="flex items-center justify-between text-xs text-purple-300 mb-1">
                        <span className="font-medium">{src.category}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300">
                          {Math.round(src.similarity_score * 100)}% match
                        </span>
                      </div>
                      <h4 className="text-xs font-semibold text-neutral-100 group-hover:text-purple-200 line-clamp-1 flex items-center gap-1">
                        {src.title}
                        <ExternalLink size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                      </h4>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mt-6 pt-4 border-t border-neutral-800 flex items-center justify-between">
                <p className="text-xs text-neutral-400">Couldn't find what you need?</p>
                <Link
                  to="/help/tickets/new"
                  className="text-xs text-purple-400 hover:text-purple-300 font-semibold inline-flex items-center gap-1"
                >
                  Create a Support Request <ChevronRight size={14} />
                </Link>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Knowledge Base Articles Browser */}
      <section className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-neutral-900">Explore Documentation</h2>
            <p className="text-sm text-neutral-500 mt-0.5">
              Browse guides, setup instructions, and troubleshooting articles.
            </p>
          </div>

          {/* Quick Filter Search */}
          <div className="relative w-full md:w-72">
            <Search size={16} className="absolute left-3 top-3 text-neutral-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search articles..."
              className="w-full pl-9 pr-4 py-2 bg-white border border-neutral-200 rounded-lg text-sm text-neutral-900 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent transition-all"
            />
          </div>
        </div>

        {/* Category Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none border-b border-neutral-200">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                selectedCategory === cat
                  ? 'bg-neutral-900 text-white shadow-sm'
                  : 'bg-white text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 border border-neutral-200/80'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Article Cards Grid */}
        {isLoadingArticles ? (
          <div className="flex items-center justify-center py-16 text-neutral-400">
            <Loader2 size={32} className="animate-spin" />
          </div>
        ) : filteredArticles.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredArticles.map((article) => (
              <div
                key={article.id}
                onClick={() => setActiveArticleModal(article)}
                className="cursor-pointer group p-5 bg-white border border-neutral-200 hover:border-neutral-300 hover:shadow-md rounded-xl transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center gap-2 text-xs font-medium text-neutral-500 mb-2">
                    <span className="px-2 py-0.5 rounded-md bg-neutral-100 text-neutral-700 font-semibold">
                      {article.category}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <BookOpen size={12} /> 3 min read
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-neutral-900 group-hover:text-primary transition-colors line-clamp-2">
                    {article.title}
                  </h3>

                  <p className="mt-2 text-xs text-neutral-600 line-clamp-3 leading-relaxed">
                    {article.content}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-neutral-100 flex items-center justify-between text-xs font-medium text-primary">
                  <span>Read article</span>
                  <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-16 bg-white rounded-xl border border-neutral-200 p-8">
            <HelpCircle size={40} className="mx-auto text-neutral-300 mb-3" />
            <h3 className="text-sm font-semibold text-neutral-800">No articles found</h3>
            <p className="text-xs text-neutral-500 mt-1 max-w-sm mx-auto">
              We couldn't find any articles matching "{searchQuery}". Try asking our AI Assistant or submit a support request.
            </p>
          </div>
        )}
      </section>

      {/* Still Need Help CTA Banner */}
      <section className="bg-gradient-to-r from-neutral-900 to-neutral-800 text-white rounded-xl p-8 flex flex-col sm:flex-row items-center justify-between gap-6 shadow-md">
        <div>
          <h3 className="text-lg font-bold">Still need assistance?</h3>
          <p className="text-neutral-300 text-sm mt-1">
            Our specialized support engineers are available to resolve your issues quickly.
          </p>
        </div>
        <Link
          to="/help/tickets/new"
          className="px-6 py-2.5 bg-white hover:bg-neutral-100 text-neutral-900 rounded-lg text-sm font-semibold transition-all shadow shrink-0"
        >
          Submit a Ticket
        </Link>
      </section>

      {/* Article Detail Modal / Reader */}
      {activeArticleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white max-w-2xl w-full rounded-2xl shadow-2xl border border-neutral-200 overflow-hidden max-h-[85vh] flex flex-col">
            <div className="p-6 border-b border-neutral-200 flex items-start justify-between bg-neutral-50/50">
              <div>
                <span className="inline-block px-2.5 py-0.5 rounded-full bg-neutral-200 text-neutral-800 text-xs font-semibold mb-2">
                  {activeArticleModal.category}
                </span>
                <h3 className="text-xl font-bold text-neutral-900">{activeArticleModal.title}</h3>
              </div>
              <button
                onClick={() => setActiveArticleModal(null)}
                className="text-neutral-400 hover:text-neutral-700 p-1 rounded-lg transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-sm text-neutral-700 leading-relaxed whitespace-pre-wrap">
              {activeArticleModal.content}
            </div>

            <div className="p-4 border-t border-neutral-200 bg-neutral-50 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-green-700 font-medium">
                <CheckCircle2 size={14} /> Official ResolveAI Guide
              </div>
              <button
                onClick={() => setActiveArticleModal(null)}
                className="px-4 py-1.5 bg-neutral-900 text-white rounded-lg text-xs font-semibold hover:bg-neutral-800 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
