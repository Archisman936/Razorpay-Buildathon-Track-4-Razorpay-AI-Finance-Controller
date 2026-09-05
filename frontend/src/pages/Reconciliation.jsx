import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GitMerge, Play, ChevronDown, ChevronUp, Info, MessageSquare, X } from 'lucide-react';
import { reconciliationApi } from '../api.js';

const SOURCE_TYPES = ['bank_record', 'payment', 'order', 'settlement'];

function formatINR(v) {
  if (v == null) return '—';
  return '₹' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function StatusBadge({ status }) {
  if (!status) return null;
  const s = status.toLowerCase();
  const cls = s.includes('exact') ? 'badge-matched'
    : s.includes('match') && !s.includes('un') ? 'badge-matched'
    : s.includes('unmatch') ? 'badge-unmatched'
    : s.includes('review') || s.includes('ambigu') ? 'badge-review'
    : 'badge-pending';
  return <span className={`badge ${cls}`}>{status}</span>;
}

function Gauge({ value, label, color }) {
  const pct = (value * 100).toFixed(1);
  return (
    <div style={{ marginBottom: 'var(--space-sm)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
        <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontWeight: 700, color }}>{pct}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function DetailModal({ result, onClose, onAskAI }) {
  const [showCandidates, setShowCandidates] = useState(false);
  if (!result) return null;

  const facts = result.explanation_facts || {};

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--space-md)',
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-normal)',
        width: '100%', maxWidth: 760,
        maxHeight: '90vh', overflow: 'auto',
        boxShadow: 'var(--shadow-lg)',
      }}>
        {/* Modal header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: 'var(--space-lg)', borderBottom: '1px solid var(--border-subtle)',
          position: 'sticky', top: 0, background: 'var(--bg-card)', zIndex: 1,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h3 style={{ fontSize: 15 }}>Reconciliation Detail</h3>
            <StatusBadge status={result.status} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onAskAI(result)}
              title="Ask the AI about this record"
            >
              <MessageSquare size={14} /> Ask AI
            </button>
            <button className="btn btn-ghost btn-sm" onClick={onClose}>
              <X size={16} />
            </button>
          </div>
        </div>

        <div style={{ padding: 'var(--space-lg)' }}>
          {/* Case info */}
          <div style={{
            padding: '8px 12px', borderRadius: 'var(--radius-sm)',
            background: 'var(--bg-elevated)', marginBottom: 'var(--space-lg)',
            fontSize: 12, color: 'var(--text-muted)',
          }}>
            Case ID: <strong style={{ color: 'var(--text-secondary)' }}>{result.case_id}</strong>
            &nbsp;·&nbsp;Method:{' '}
            <span className="badge badge-blue" style={{ fontSize: 11 }}>
              {result.reconciliation_method}
            </span>
          </div>

          <div className="grid-2">
            {/* SOURCE */}
            <div className="card">
              <h4 style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-md)' }}>
                Source Record
              </h4>
              {[
                ['Record ID', result.source_record_id],
                ['Source Type', result.source_type],
                ['Bank Amount', facts.bank_amount != null ? formatINR(facts.bank_amount) : null],
                ['Transaction Date', facts.transaction_date],
                ['Reference', facts.bank_reference || facts.utr],
                ['Merchant', facts.merchant_id],
              ].filter(([, v]) => v != null).map(([k, v]) => (
                <div key={k} style={{
                  display: 'flex', justifyContent: 'space-between', padding: '6px 0',
                  borderBottom: '1px solid var(--border-subtle)', fontSize: 12,
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500, textAlign: 'right', maxWidth: '60%', wordBreak: 'break-all' }}>
                    {String(v)}
                  </span>
                </div>
              ))}
            </div>

            {/* MATCH */}
            <div className="card">
              <h4 style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-md)' }}>
                Match Details
              </h4>
              {[
                ['Matched Record', result.matched_record_id],
                ['Settlement Amount', facts.settlement_net_amount != null ? formatINR(facts.settlement_net_amount) : null],
                ['Settlement UTR', facts.settlement_utr],
                ['Amount Difference', result.amount_difference != null ? formatINR(result.amount_difference) : null],
                ['Date Difference', result.date_difference != null ? `${result.date_difference} day(s)` : null],
                ['Merchant Match', facts.merchant_match != null ? (facts.merchant_match ? '✓ Yes' : '✗ No') : null],
              ].filter(([, v]) => v != null).map(([k, v]) => (
                <div key={k} style={{
                  display: 'flex', justifyContent: 'space-between', padding: '6px 0',
                  borderBottom: '1px solid var(--border-subtle)', fontSize: 12,
                }}>
                  <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500, textAlign: 'right', maxWidth: '60%', wordBreak: 'break-all' }}>
                    {String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ML Confidence */}
          {(result.match_probability != null || result.exception_type) && (
            <div className="card" style={{ marginTop: 'var(--space-md)' }}>
              <h4 style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-md)' }}>
                ML Confidence
              </h4>
              {result.match_probability != null && (
                <Gauge value={result.match_probability} label="Match Probability" color="var(--status-matched)" />
              )}
              {result.runner_up_probability != null && (
                <Gauge value={result.runner_up_probability} label="Runner-up Probability" color="var(--brand-amber)" />
              )}
              {result.confidence_margin != null && (
                <Gauge value={result.confidence_margin} label="Confidence Margin" color="var(--brand-indigo)" />
              )}
              {result.exception_type && (
                <div style={{ marginTop: 'var(--space-md)', padding: 10, background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', fontSize: 12 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Exception: </span>
                  <span style={{ color: 'var(--brand-amber)', fontWeight: 600 }}>{result.exception_type}</span>
                  {result.exception_confidence != null && (
                    <span style={{ color: 'var(--text-muted)' }}> ({(result.exception_confidence * 100).toFixed(0)}% confidence)</span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Reason codes */}
          {result.reason_codes?.length > 0 && (
            <div className="card" style={{ marginTop: 'var(--space-md)' }}>
              <h4 style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-sm)' }}>
                Reason Codes
              </h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {result.reason_codes.map(code => (
                  <span key={code} className="badge badge-pending">{code}</span>
                ))}
              </div>
            </div>
          )}

          {/* Financial context (explanation_facts) */}
          {Object.keys(facts).length > 0 && (
            <div className="card" style={{ marginTop: 'var(--space-md)' }}>
              <h4 style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 'var(--space-sm)' }}>
                Financial Context
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {Object.entries(facts).map(([k, v]) => (
                  <div key={k} style={{
                    display: 'flex', justifyContent: 'space-between', padding: '5px 0',
                    borderBottom: '1px solid var(--border-subtle)', fontSize: 12,
                  }}>
                    <span style={{ color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                      {k.replace(/_/g, ' ')}
                    </span>
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 500, textAlign: 'right', maxWidth: '65%', wordBreak: 'break-all' }}>
                      {typeof v === 'boolean' ? (v ? '✓ Yes' : '✗ No') : String(v ?? '—')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Candidates */}
          {result.candidate_records?.length > 0 && (
            <div className="card" style={{ marginTop: 'var(--space-md)' }}>
              <button
                className="btn btn-ghost btn-sm"
                style={{ width: '100%', justifyContent: 'space-between' }}
                onClick={() => setShowCandidates(v => !v)}
              >
                <span><Info size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />
                  Candidate Records ({result.candidate_records.length})
                </span>
                {showCandidates ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {showCandidates && (
                <div className="table-wrap" style={{ marginTop: 'var(--space-md)' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        {Object.keys(result.candidate_records[0]).slice(0, 6).map(k => (
                          <th key={k}>{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.candidate_records.map((row, i) => (
                        <tr key={i}>
                          {Object.values(row).slice(0, 6).map((v, j) => (
                            <td key={j}>{v == null ? '—' : String(v)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Ask AI footer */}
          <div style={{
            marginTop: 'var(--space-lg)', padding: 'var(--space-md)',
            borderRadius: 'var(--radius-md)', background: 'rgba(99,102,241,0.08)',
            border: '1px solid rgba(99,102,241,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            gap: 'var(--space-md)', flexWrap: 'wrap',
          }}>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              <strong style={{ color: 'var(--text-accent)' }}>Ask the AI</strong> about this record
              — get a detailed explanation powered by Gemini + RAG
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => onAskAI(result)}>
              <MessageSquare size={14} /> Ask AI
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Reconciliation() {
  const navigate = useNavigate();
  const [sourceType, setSourceType] = useState('bank_record');
  const [sourceId, setSourceId] = useState('');
  const [includeMl, setIncludeMl] = useState(true);
  const [includeException, setIncludeException] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [showDetail, setShowDetail] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!sourceId.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await reconciliationApi.run(sourceType, sourceId.trim(), includeMl, includeException);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleAskAI(r) {
    const question = `Explain the reconciliation result for ${r.source_type} ${r.source_record_id}. Status: ${r.status}. Matched to: ${r.matched_record_id || 'none'}. Method: ${r.reconciliation_method}.`;
    navigate('/chat', { state: { prefill: question } });
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Reconciliation Engine</h1>
        <p>Run deterministic + ML reconciliation on any bank, payment, order, or settlement record</p>
      </div>

      {/* Form */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--space-lg)' }}>
          <GitMerge size={18} style={{ color: 'var(--brand-indigo)' }} />
          <h3 style={{ fontSize: 15 }}>Run Reconciliation</h3>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="recon-form">
            <div className="input-group">
              <label className="input-label" htmlFor="source-type">Source Type</label>
              <select
                id="source-type"
                className="select"
                value={sourceType}
                onChange={e => setSourceType(e.target.value)}
              >
                {SOURCE_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="input-group">
              <label className="input-label" htmlFor="source-id">Source ID</label>
              <input
                id="source-id"
                className="input"
                placeholder="e.g. BNK_000001"
                value={sourceId}
                onChange={e => setSourceId(e.target.value)}
                required
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-lg)', marginTop: 'var(--space-md)' }}>
            {[
              { id: 'include-ml',  label: 'Include ML Scoring',          value: includeMl,        set: setIncludeMl },
              { id: 'include-exc', label: 'Include Exception Classifier', value: includeException, set: setIncludeException },
            ].map(({ id, label, value, set }) => (
              <label key={id} htmlFor={id} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
                <input id={id} type="checkbox" checked={value} onChange={e => set(e.target.checked)} style={{ accentColor: 'var(--brand-indigo)' }} />
                {label}
              </label>
            ))}
          </div>

          <div style={{ marginTop: 'var(--space-lg)' }}>
            <button type="submit" className="btn btn-primary" disabled={loading || !sourceId.trim()}>
              {loading
                ? <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Running…</>
                : <><Play size={16} /> Run Reconciliation</>
              }
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 'var(--space-md)' }}>{error}</div>
      )}

      {/* Result summary card */}
      {result && (
        <div className="card" style={{ marginBottom: 'var(--space-md)', animation: 'fadeIn 0.3s ease' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-md)' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <h3 style={{ fontSize: 16 }}>Reconciliation Result</h3>
                <StatusBadge status={result.status} />
                <span className="badge badge-blue" style={{ fontSize: 11 }}>{result.reconciliation_method}</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Case: <strong style={{ color: 'var(--text-secondary)' }}>{result.case_id}</strong>
              </p>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowDetail(true)}>
                <Info size={14} /> View Details
              </button>
              <button className="btn btn-primary btn-sm" onClick={() => handleAskAI(result)}>
                <MessageSquare size={14} /> Ask AI
              </button>
            </div>
          </div>

          {/* Quick stats row */}
          <div style={{ display: 'flex', gap: 'var(--space-md)', marginTop: 'var(--space-md)', flexWrap: 'wrap' }}>
            {[
              { label: 'Source', value: result.source_record_id },
              { label: 'Matched To', value: result.matched_record_id || '—' },
              { label: 'Amount Diff', value: result.amount_difference != null ? `₹${result.amount_difference.toFixed(2)}` : '—' },
              { label: 'Date Diff', value: result.date_difference != null ? `${result.date_difference}d` : '—' },
            ].map(({ label, value }) => (
              <div key={label} style={{
                padding: '8px 14px', borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 2, fontFamily: 'monospace' }}>{value}</div>
              </div>
            ))}
          </div>

          {result.reason_codes?.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 'var(--space-md)' }}>
              {result.reason_codes.map(code => (
                <span key={code} className="badge badge-pending">{code}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {!result && !loading && !error && (
        <div className="card">
          <div className="empty-state">
            <GitMerge size={40} />
            <h3>No result yet</h3>
            <p>Enter a Source Type and Source ID above, then click Run Reconciliation to see the full deterministic + ML result.</p>
            <p style={{ fontSize: 12, marginTop: 'var(--space-sm)', color: 'var(--text-muted)' }}>
              Try: <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>BNK_000001</code> with Source Type <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>bank_record</code>
            </p>
          </div>
        </div>
      )}

      {/* Detail modal */}
      {showDetail && result && (
        <DetailModal
          result={result}
          onClose={() => setShowDetail(false)}
          onAskAI={(r) => { setShowDetail(false); handleAskAI(r); }}
        />
      )}
    </div>
  );
}
