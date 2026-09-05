import { useState } from 'react';
import { Search, Database, Hash } from 'lucide-react';
import { transactionsApi } from '../api.js';

const SOURCE_TYPES = ['bank', 'payment', 'order', 'settlement'];

function RecordTable({ record }) {
  if (!record) return null;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(record).map(([key, value]) => (
            <tr key={key}>
              <td style={{ color: 'var(--text-muted)', fontWeight: 500, whiteSpace: 'nowrap' }}>{key}</td>
              <td style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                {value == null ? <span style={{ color: 'var(--text-muted)' }}>—</span> : String(value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Transactions() {
  const [sourceType, setSourceType] = useState('payment');
  const [sourceId, setSourceId] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!sourceId.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await transactionsApi.get(sourceType, sourceId.trim());
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Transaction Lookup</h1>
        <p>Fetch a single bank record, payment, order, or settlement from the PostgreSQL database</p>
      </div>

      {/* Form */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--space-lg)' }}>
          <Database size={18} style={{ color: 'var(--brand-cyan)' }} />
          <h3 style={{ fontSize: 15 }}>Lookup Record</h3>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="recon-form">
            <div className="input-group">
              <label className="input-label" htmlFor="txn-type">Record Type</label>
              <select
                id="txn-type"
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
              <label className="input-label" htmlFor="txn-id">Record ID</label>
              <input
                id="txn-id"
                className="input"
                placeholder="e.g. pay_QrT8Mk3fXp or BNK_000042"
                value={sourceId}
                onChange={e => setSourceId(e.target.value)}
                required
              />
            </div>
          </div>
          <div style={{ marginTop: 'var(--space-lg)' }}>
            <button type="submit" className="btn btn-primary" disabled={loading || !sourceId.trim()}>
              {loading
                ? <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Fetching…</>
                : <><Search size={16} /> Fetch Record</>
              }
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 'var(--space-md)' }}>
          {error}
        </div>
      )}

      {result && (
        <div className="card" style={{ animation: 'fadeIn 0.4s ease' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 'var(--space-md)' }}>
            <Hash size={14} style={{ color: 'var(--brand-cyan)' }} />
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Type:</span>
            <span className="badge badge-blue">{result.source_type}</span>
          </div>
          <RecordTable record={result.record} />
        </div>
      )}

      {!result && !loading && !error && (
        <div className="card">
          <div className="empty-state">
            <Database size={40} />
            <h3>No record fetched</h3>
            <p>Select a record type and enter an ID to retrieve detailed transaction data from the database.</p>
          </div>
        </div>
      )}
    </div>
  );
}
