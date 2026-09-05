import { useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Upload, FileText, X, CheckCircle2, AlertTriangle, CloudUpload, Info } from 'lucide-react';
import { uploadApi } from '../api.js';

const ACCEPTED_EXTS = ['.csv', '.xlsx', '.xls', '.pdf', '.jsonl', '.json'];
const ACCEPT_ATTR = ACCEPTED_EXTS.join(',');

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileItem({ file, result, error, onRemove }) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  const extColor = {
    '.csv': 'var(--brand-emerald)',
    '.xlsx': 'var(--brand-teal)',
    '.xls': 'var(--brand-teal)',
    '.pdf': 'var(--brand-rose)',
    '.jsonl': 'var(--brand-indigo)',
    '.json': 'var(--brand-indigo)',
  }[ext] || 'var(--text-muted)';

  return (
    <div className="card" style={{ marginBottom: 'var(--space-sm)', padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 'var(--radius-sm)',
          background: `${extColor}22`, display: 'flex', alignItems: 'center',
          justifyContent: 'center', flexShrink: 0,
        }}>
          <FileText size={18} style={{ color: extColor }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)', wordBreak: 'break-all' }}>
            {file.name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            {formatBytes(file.size)} · {ext.toUpperCase().replace('.', '')}
          </div>

          {/* Result */}
          {result && (
            <div style={{
              marginTop: 10, padding: '10px 12px',
              background: 'rgba(16,185,129,0.08)', borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(16,185,129,0.2)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <CheckCircle2 size={14} style={{ color: 'var(--status-matched)' }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--status-matched)' }}>
                  Processed Successfully
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                <div><strong>Live in PostgreSQL:</strong> <span style={{ color: 'var(--status-matched)', fontWeight: 600 }}>{result.inserted_records ?? result.valid_records} records ingested</span></div>
                <div><strong>Detected Schema:</strong> {result.detected_schema}</div>
                {result.inserted_ids?.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <strong>Ingested Record IDs:</strong>{' '}
                    <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--brand-emerald)', background: 'rgba(16,185,129,0.1)', padding: '2px 6px', borderRadius: 4 }}>
                      {result.inserted_ids.slice(0, 5).join(', ')}
                      {result.inserted_ids.length > 5 ? ` +${result.inserted_ids.length - 5} more` : ''}
                    </span>
                  </div>
                )}
                {result.parse_errors > 0 && (
                  <div style={{ color: 'var(--brand-amber)' }}>
                    <strong>Parse Errors:</strong> {result.parse_errors}
                  </div>
                )}
                {result.sample_fields?.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <strong>Fields:</strong>{' '}
                    <span style={{ fontFamily: 'monospace', fontSize: 11, opacity: 0.8 }}>
                      {result.sample_fields.slice(0, 6).join(', ')}
                      {result.sample_fields.length > 6 ? ` +${result.sample_fields.length - 6} more` : ''}
                    </span>
                  </div>
                )}
                {result.inserted_ids?.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Link
                      to={`/reconciliation`}
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: 11, padding: '4px 10px', textDecoration: 'none', display: 'inline-flex' }}
                    >
                      Reconcile Ingested Record ({result.inserted_ids[0]}) →
                    </Link>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{
              marginTop: 8, padding: '8px 12px',
              background: 'rgba(244,63,94,0.08)', borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(244,63,94,0.2)',
              fontSize: 12, color: 'var(--status-unmatched)',
            }}>
              <AlertTriangle size={12} style={{ display: 'inline', marginRight: 4 }} />
              {error}
            </div>
          )}
        </div>
        <button
          onClick={onRemove}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)', padding: 4, borderRadius: 4,
          }}
          title="Remove file"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}

export default function UploadData() {
  const [files, setFiles] = useState([]);
  const [sourceType, setSourceType] = useState('auto_detect');
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState({});
  const [errors, setErrors] = useState({});
  const [dragOver, setDragOver] = useState(false);
  const [overallSuccess, setOverallSuccess] = useState(false);
  const fileInputRef = useRef(null);

  const SOURCE_TYPES = [
    'auto_detect', 'bank_record', 'payment', 'order', 'settlement',
    'invoice', 'refund', 'fee', 'gst', 'book', 'adjustment',
  ];

  const addFiles = useCallback((newFiles) => {
    const valid = Array.from(newFiles).filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase();
      return ACCEPTED_EXTS.includes(ext);
    });
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name + f.size));
      return [...prev, ...valid.filter(f => !existing.has(f.name + f.size))];
    });
  }, []);

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  function handleRemove(index) {
    const file = files[index];
    setFiles(prev => prev.filter((_, i) => i !== index));
    setResults(prev => { const n = { ...prev }; delete n[file.name + file.size]; return n; });
    setErrors(prev => { const n = { ...prev }; delete n[file.name + file.size]; return n; });
  }

  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    setOverallSuccess(false);
    const newResults = {};
    const newErrors = {};

    for (const file of files) {
      const key = file.name + file.size;
      try {
        const res = await uploadApi.uploadFile(file, sourceType);
        newResults[key] = res;
      } catch (err) {
        newErrors[key] = err.message;
      }
    }

    setResults(newResults);
    setErrors(newErrors);
    setUploading(false);
    setOverallSuccess(Object.keys(newResults).length > 0);
  }

  const totalRecords = Object.values(results).reduce((s, r) => s + (r?.valid_records || 0), 0);
  const hasFiles = files.length > 0;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Upload Data</h1>
        <p>Upload CSV, XLSX, XLS, PDF, or JSONL files to ingest into the reconciliation pipeline</p>
      </div>

      {/* Info banner */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        padding: '12px 16px', borderRadius: 'var(--radius-md)',
        background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
        marginBottom: 'var(--space-xl)', fontSize: 13, color: 'var(--text-secondary)',
      }}>
        <Info size={15} style={{ color: 'var(--brand-indigo)', marginTop: 1, flexShrink: 0 }} />
        <span>
          Uploaded files are parsed by the existing normalization pipeline. The backend will detect
          the schema automatically, or you can specify a source type. Records are validated and
          summarized below.
        </span>
      </div>

      {/* Source type selector */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <h3 style={{ fontSize: 14, marginBottom: 'var(--space-md)' }}>Upload Settings</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
          <div className="input-group" style={{ flex: '0 0 260px' }}>
            <label className="input-label">Data Source Type</label>
            <select
              className="select"
              value={sourceType}
              onChange={e => setSourceType(e.target.value)}
            >
              {SOURCE_TYPES.map(t => (
                <option key={t} value={t}>
                  {t === 'auto_detect' ? '🔍 Auto Detect' : t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 20 }}>
            Select "Auto Detect" to let the backend identify the schema from file contents.
          </p>
        </div>
      </div>

      {/* Drop zone */}
      <div
        className="card"
        style={{
          marginBottom: 'var(--space-xl)',
          border: dragOver ? '2px dashed var(--brand-indigo)' : '2px dashed var(--border-normal)',
          background: dragOver ? 'rgba(99,102,241,0.05)' : 'var(--bg-card)',
          transition: 'all var(--transition-fast)',
          cursor: 'pointer',
        }}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="empty-state" style={{ padding: 'var(--space-2xl) 0' }}>
          <CloudUpload
            size={48}
            style={{ color: dragOver ? 'var(--brand-indigo)' : 'var(--text-muted)', marginBottom: 12 }}
          />
          <h3 style={{ fontSize: 16 }}>
            {dragOver ? 'Drop files here…' : 'Drag & drop files here'}
          </h3>
          <p style={{ fontSize: 13 }}>
            or{' '}
            <span style={{ color: 'var(--brand-indigo)', fontWeight: 600 }}>browse files</span>
          </p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            Supported: CSV, XLSX, XLS, PDF, JSONL, JSON
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPT_ATTR}
          style={{ display: 'none' }}
          onChange={e => addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {hasFiles && (
        <div style={{ marginBottom: 'var(--space-xl)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
            <h3 style={{ fontSize: 14 }}>
              Selected Files ({files.length})
            </h3>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => { setFiles([]); setResults({}); setErrors({}); setOverallSuccess(false); }}
            >
              <X size={14} /> Clear All
            </button>
          </div>

          {files.map((file, i) => (
            <FileItem
              key={file.name + file.size}
              file={file}
              result={results[file.name + file.size]}
              error={errors[file.name + file.size]}
              onRemove={() => handleRemove(i)}
            />
          ))}

          <div style={{ marginTop: 'var(--space-lg)' }}>
            <button
              className="btn btn-primary"
              onClick={handleUpload}
              disabled={uploading || files.length === 0}
            >
              {uploading
                ? <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Processing…</>
                : <><Upload size={16} /> Upload & Process {files.length} file{files.length !== 1 ? 's' : ''}</>
              }
            </button>
          </div>
        </div>
      )}

      {/* Success summary */}
      {overallSuccess && (
        <div style={{
          padding: '16px 20px', borderRadius: 'var(--radius-md)',
          background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
          marginBottom: 'var(--space-xl)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <CheckCircle2 size={18} style={{ color: 'var(--status-matched)' }} />
            <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--status-matched)' }}>
              Upload Complete
            </span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Successfully parsed <strong>{totalRecords.toLocaleString()}</strong> records
            across {Object.keys(results).length} file{Object.keys(results).length !== 1 ? 's' : ''}.
            Check the Dashboard to see updated metrics.
          </p>
        </div>
      )}

      {/* Processing flow info */}
      {!hasFiles && (
        <div className="card">
          <h3 style={{ fontSize: 14, marginBottom: 'var(--space-lg)' }}>Upload Processing Flow</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            {[
              { step: 'File Upload', desc: 'Your file is securely received by FastAPI', color: 'var(--brand-indigo)' },
              { step: 'Schema Detection', desc: 'Auto-detects data type from field fingerprints', color: 'var(--brand-blue)' },
              { step: 'Parsing', desc: 'CSV, Excel, PDF, or JSON parsed into records', color: 'var(--brand-cyan)' },
              { step: 'Validation', desc: 'Fields validated: amounts, dates, references', color: 'var(--brand-teal)' },
              { step: 'Normalization', desc: 'Canonical transforms applied to all fields', color: 'var(--brand-emerald)' },
              { step: 'Results', desc: 'Record count and schema summary returned', color: 'var(--brand-amber)' },
            ].map(({ step, desc, color }, i) => (
              <div key={step} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 'var(--radius-full)',
                  background: `${color}22`, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 12, fontWeight: 700,
                  color, flexShrink: 0,
                }}>
                  {i + 1}
                </div>
                <div style={{ paddingTop: 4 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{step}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
