import { useState, useEffect } from 'react';
import { Activity, RefreshCw, Database, Cpu, Brain, Wifi, CheckCircle2, XCircle } from 'lucide-react';
import { healthApi, chatApi } from '../api.js';

function StatusIcon({ ok }) {
  return ok
    ? <CheckCircle2 size={18} style={{ color: 'var(--status-matched)' }} />
    : <XCircle size={18} style={{ color: 'var(--status-unmatched)' }} />;
}

function HealthCard({ icon: Icon, title, status, ok, children, color }) {
  return (
    <div className="card" style={{ borderTop: `2px solid ${ok ? 'var(--status-matched)' : 'var(--status-unmatched)'}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 'var(--space-md)' }}>
        <div style={{
          width: 36, height: 36, borderRadius: 'var(--radius-md)',
          background: ok ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.12)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={18} style={{ color: ok ? 'var(--status-matched)' : 'var(--status-unmatched)' }} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
          <div style={{ fontSize: 12, color: ok ? 'var(--status-matched)' : 'var(--status-unmatched)', fontWeight: 500 }}>{status}</div>
        </div>
        <StatusIcon ok={ok} />
      </div>
      {children}
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border-subtle)', fontSize: 12 }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ color: 'var(--text-secondary)', fontWeight: 500, textAlign: 'right', maxWidth: '65%', wordBreak: 'break-all' }}>
        {value == null ? '—' : String(value)}
      </span>
    </div>
  );
}

export default function Health() {
  const [health, setHealth] = useState(null);
  const [chatHealth, setChatHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState(null);

  async function fetchAll() {
    setLoading(true);
    const [h, ch] = await Promise.allSettled([
      healthApi.get(),
      chatApi.health(),
    ]);
    setHealth(h.status === 'fulfilled' ? h.value : { status: 'error', error: h.reason?.message });
    setChatHealth(ch.status === 'fulfilled' ? ch.value : { ok: false, error: ch.reason?.message });
    setLastChecked(new Date());
    setLoading(false);
  }

  useEffect(() => { fetchAll(); }, []);

  const dbOk = health?.database?.ok === true;
  const reconOk = !!health?.models?.reconciliation_schema;
  const excOk = !!health?.models?.exception_schema;
  const overallOk = health?.status === 'ok';
  const llmOk = chatHealth?.ok === true || chatHealth?.components?.gemini?.ok === true;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>System Health</h1>
        <p>Live status of database, ML models, LLM service, and API endpoints</p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
        {/* Overall badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px',
          background: overallOk ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
          border: `1px solid ${overallOk ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'}`,
          borderRadius: 'var(--radius-lg)', fontSize: 14, fontWeight: 600,
        }}>
          <div className={`status-dot ${overallOk ? 'ok' : 'error'}`} style={{ width: 10, height: 10 }} />
          <span style={{ color: overallOk ? 'var(--status-matched)' : 'var(--status-unmatched)' }}>
            System {overallOk ? 'Operational' : loading ? 'Checking…' : 'Degraded'}
          </span>
        </div>

        <button className="btn btn-secondary btn-sm" onClick={fetchAll} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-pulse' : ''} /> Refresh
        </button>

        {lastChecked && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Last checked: {lastChecked.toLocaleTimeString()}
          </span>
        )}
      </div>

      {loading && !health && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 'var(--space-xl)', color: 'var(--text-muted)' }}>
          <div className="spinner spinner-lg" />
          <span>Fetching health data…</span>
        </div>
      )}

      {health && (
        <div className="grid-2" style={{ marginBottom: 'var(--space-xl)' }}>
          {/* Database */}
          <HealthCard icon={Database} title="PostgreSQL Database" ok={dbOk} status={dbOk ? 'Connected' : 'Disconnected'}>
            {health.database && Object.entries(health.database).map(([k, v]) => (
              <DetailRow key={k} label={k} value={typeof v === 'boolean' ? (v ? 'Yes' : 'No') : v} />
            ))}
          </HealthCard>

          {/* LLM / Chat */}
          <HealthCard icon={Wifi} title="Gemini LLM Service" ok={llmOk} status={llmOk ? 'Online' : 'Unavailable'}>
            <DetailRow label="Service Status" value={llmOk ? 'Online' : 'Unavailable'} />
            <DetailRow label="Model" value={chatHealth?.components?.gemini?.model || 'gemini-3.1-flash-lite'} />
            <DetailRow label="Gemini API" value={chatHealth?.components?.gemini?.ok ? 'Connected' : (chatHealth?.components?.gemini?.error || 'Unavailable')} />
            <DetailRow label="RAG Knowledge Base" value={chatHealth?.components?.rag?.vector_store?.ok ? `${chatHealth?.components?.rag?.vector_store?.document_count || 162} chunks indexed` : 'Unavailable'} />
            <DetailRow label="Embedding Model" value={chatHealth?.components?.rag?.config?.embedding_model || 'all-MiniLM-L6-v2'} />
            <DetailRow label="Conversation History" value={`${chatHealth?.conversation_history_length ?? 0} messages`} />
          </HealthCard>

          {/* Reconciliation ML */}
          <HealthCard icon={Cpu} title="Reconciliation ML Model" ok={reconOk} status={reconOk ? 'Loaded' : 'Not Found'}>
            <DetailRow label="Schema loaded" value={reconOk ? 'Yes' : 'No'} />
            <DetailRow label="Model file" value="best_reconciliation_model.joblib" />
            <DetailRow label="Algorithm" value="Logistic Regression (Binary Classifier)" />
            <DetailRow label="Type" value="Binary Classifier (Match / Unmatch)" />
          </HealthCard>

          {/* Exception ML */}
          <HealthCard icon={Brain} title="Exception Classifier" ok={excOk} status={excOk ? 'Loaded' : 'Not Found'}>
            <DetailRow label="Schema loaded" value={excOk ? 'Yes' : 'No'} />
            <DetailRow label="Model file" value="best_exception_classifier.joblib" />
            <DetailRow label="Algorithm" value="Logistic Regression (Multi-Class Classifier)" />
            <DetailRow label="Type" value="Multi-Class Classifier (7 Exception Classes)" />
            <DetailRow label="Purpose" value="Exception type classification" />
          </HealthCard>
        </div>
      )}

      {/* Raw JSON */}
      {health && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--space-md)' }}>
            <Activity size={16} style={{ color: 'var(--brand-indigo)' }} />
            <h3 style={{ fontSize: 14 }}>Raw Health Response</h3>
          </div>
          <pre style={{ maxHeight: 300, overflow: 'auto' }}>
            {JSON.stringify({ backend: health, llm: chatHealth }, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
