import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { Send, RefreshCw, Bot, Sparkles, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { chatApi } from '../api.js';

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function TypingIndicator() {
  return (
    <div className="chat-bubble agent">
      <div className="chat-bubble-inner">
        <div className="typing-indicator">
          <div className="typing-dot" />
          <div className="typing-dot" />
          <div className="typing-dot" />
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  const [showSources, setShowSources] = useState(false);
  const hasSources = msg.sources?.length > 0;

  return (
    <div className={`chat-bubble ${isUser ? 'user' : 'agent'}`}>
      <div className="chat-bubble-inner">
        {!isUser && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Bot size={14} style={{ color: 'var(--brand-indigo)' }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-accent)' }}>Gemini AI</span>
            {msg.tools_used?.length > 0 && (
              <span style={{
                fontSize: 10, color: 'var(--text-muted)',
                background: 'var(--bg-base)', padding: '1px 6px',
                borderRadius: 'var(--radius-full)',
              }}>
                🔧 {msg.tools_used.join(', ')}
              </span>
            )}
          </div>
        )}

        <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, fontSize: 14 }}>
          {msg.content}
        </div>

        {/* Confidence */}
        {msg.confidence != null && (
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            Confidence:{' '}
            <span style={{ color: msg.confidence > 0.7 ? 'var(--status-matched)' : 'var(--status-review)' }}>
              {(msg.confidence * 100).toFixed(0)}%
            </span>
          </div>
        )}

        {/* Sources accordion */}
        {hasSources && (
          <div style={{ marginTop: 10 }}>
            <button
              className="btn btn-ghost btn-sm"
              style={{ fontSize: 11, padding: '3px 8px' }}
              onClick={() => setShowSources(v => !v)}
            >
              <BookOpen size={11} />
              RAG Sources ({msg.sources.length})
              {showSources ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
            {showSources && (
              <div className="chat-sources" style={{ marginTop: 6 }}>
                {msg.sources.map((s, i) => (
                  <span key={i} className="chat-source-chip">
                    {s.source || s.document || s.type || `source-${i + 1}`}
                    {s.id && s.id !== 'Unknown' && ` · ${s.id}`}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="chat-meta">{formatTime(msg.timestamp)}</div>
    </div>
  );
}

const SUGGESTIONS = [
  'What is the reconciliation status of BNK_000001?',
  'Why was this transaction not reconciled?',
  'Explain how the ML reconciliation model works.',
  'What exception types does the classifier handle?',
  'What are the financial rules for MDR and GST?',
  'How are settlement timing differences flagged?',
];

const WELCOME_MSG = {
  role: 'agent',
  content: `👋 Hello! I'm the **Razorpay AI Finance Controller**, powered by **Gemini** with RAG context from your financial rules and reconciliation documentation.

I can help you:
• Explain reconciliation results for specific records
• Query transactions, payments, and settlements
• Interpret exception classifications
• Answer questions about financial rules (MDR, GST, etc.)
• Analyze discrepancies and timing differences

What would you like to know?`,
  timestamp: Date.now(),
  sources: [],
  tools_used: [],
};

export default function Chat() {
  const location = useLocation();
  const [messages, setMessages] = useState([WELCOME_MSG]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const sentPrefill = useRef(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, loading]);

  // Handle pre-filled question from reconciliation detail "Ask AI" button
  useEffect(() => {
    if (location.state?.prefill && !sentPrefill.current) {
      sentPrefill.current = true;
      sendMessage(location.state.prefill);
      // Clear state so refresh doesn't re-send
      window.history.replaceState({}, '');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  async function sendMessage(text) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput('');
    setError(null);

    const userMsg = { role: 'user', content: msg, timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await chatApi.message(msg);
      setMessages(prev => [...prev, {
        role: 'agent',
        content: res.answer || 'No response from agent.',
        sources: res.sources || [],
        tools_used: res.tools_used || [],
        confidence: res.confidence ?? null,
        metadata: res.metadata || {},
        timestamp: Date.now(),
      }]);
    } catch (err) {
      setError(err.message);
      setMessages(prev => [...prev, {
        role: 'agent',
        content: `⚠️ The AI service encountered an error: ${err.message}. Please try again.`,
        timestamp: Date.now(),
        sources: [],
        tools_used: [],
      }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleReset() {
    await chatApi.reset().catch(() => {});
    setMessages([{
      ...WELCOME_MSG,
      content: 'Conversation cleared. How can I help you?',
      timestamp: Date.now(),
    }]);
    setError(null);
    sentPrefill.current = false;
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const showSuggestions = messages.length === 1;

  return (
    <div className="chat-layout">
      {/* Topbar */}
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 36, height: 36, background: 'var(--razorpay-gradient)',
            borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Sparkles size={18} color="#fff" />
          </div>
          <div>
            <div className="topbar-title">AI Finance Assistant</div>
            <div className="topbar-subtitle">Gemini · RAG · Reconciliation Engine · PostgreSQL</div>
          </div>
        </div>
        <div className="topbar-actions">
          <button className="btn btn-ghost btn-sm" onClick={handleReset} title="Clear conversation">
            <RefreshCw size={14} /> Reset
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {/* Suggestions */}
        {showSuggestions && (
          <div style={{ maxWidth: 600, margin: '0 auto', width: '100%' }}>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 'var(--space-sm)' }}>
              Suggested questions:
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  className="btn btn-ghost"
                  style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                  onClick={() => sendMessage(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {loading && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        {error && (
          <div className="alert alert-error" style={{ maxWidth: 900, margin: '0 auto var(--space-sm)' }}>
            {error}
          </div>
        )}
        <div className="chat-input-row">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder="Ask about reconciliation, transactions, ML results, financial rules…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            style={{ resize: 'none' }}
          />
          <button
            className="btn btn-primary"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            style={{ padding: '14px 16px', borderRadius: 'var(--radius-lg)' }}
            title="Send (Enter)"
          >
            {loading ? <div className="spinner" style={{ borderTopColor: '#fff' }} /> : <Send size={18} />}
          </button>
        </div>
        <p style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
          Press{' '}
          <kbd style={{ background: 'var(--bg-elevated)', padding: '1px 5px', borderRadius: 3, border: '1px solid var(--border-normal)', fontSize: 10 }}>Enter</kbd>
          {' '}to send ·{' '}
          <kbd style={{ background: 'var(--bg-elevated)', padding: '1px 5px', borderRadius: 3, border: '1px solid var(--border-normal)', fontSize: 10 }}>Shift+Enter</kbd>
          {' '}for new line
        </p>
      </div>
    </div>
  );
}
