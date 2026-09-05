import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from 'recharts';
import {
  TrendingUp, CheckCircle2, AlertCircle, Database,
  ArrowRight, RefreshCw, IndianRupee, Layers,
} from 'lucide-react';
import { dashboardApi, healthApi } from '../api.js';

/** Format as Indian locale currency string: ₹1,24,50,000 */
function formatINR(amount) {
  if (amount == null) return '—';
  return '₹' + Number(amount).toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function formatINRShort(amount) {
  if (amount == null) return '—';
  if (amount >= 1e7) return '₹' + (amount / 1e7).toFixed(2) + ' Cr';
  if (amount >= 1e5) return '₹' + (amount / 1e5).toFixed(2) + ' L';
  return '₹' + Number(amount).toLocaleString('en-IN');
}

const STATUS_COLORS = {
  SETTLEMENT: '#10B981',
  INTEREST_CREDIT: '#6366F1',
  UTILITIES: '#F59E0B',
  RENT: '#F43F5E',
  SALARY: '#06B6D4',
  OTHER_TRANSFER: '#8B5CF6',
  SUPPLIER_PAYMENT: '#F97316',
};

const PAYMENT_STATUS_COLORS = {
  CAPTURED: '#10B981',
  FAILED: '#F43F5E',
  PENDING: '#F59E0B',
};

function KpiCard({ label, value, subtitle, icon: Icon, colorClass, onClick }) {
  return (
    <div
      className={`stat-card ${colorClass}`}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
      onClick={onClick}
    >
      <div className={`stat-icon ${colorClass}`}><Icon size={20} /></div>
      <div className="stat-body">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {subtitle && <div className="stat-change">{subtitle}</div>}
      </div>
    </div>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div style={{ marginBottom: 'var(--space-md)' }}>
      <h3 style={{ fontSize: 15 }}>{title}</h3>
      {subtitle && <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</p>}
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, h] = await Promise.all([
        dashboardApi.summary(),
        healthApi.get(),
      ]);
      setSummary(s);
      setHealth(h);
      setLastRefreshed(new Date());
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const recon = summary?.reconciliation || {};
  const total = recon.total || 0;
  const reconciled = recon.reconciled || 0;
  const unreconciled = recon.unreconciled || 0;
  const rate = recon.rate || 0;
  const discrepancy = recon.total_discrepancy_amount || 0;

  const categoryData = (summary?.category_breakdown || []).map(c => ({
    name: c.category?.replace(/_/g, ' ') || 'UNKNOWN',
    value: c.count,
    fill: STATUS_COLORS[c.category] || '#64748b',
  }));

  const pieData = [
    { name: 'Reconciled', value: reconciled, fill: '#10B981' },
    { name: 'Unreconciled', value: unreconciled, fill: '#F43F5E' },
  ].filter(d => d.value > 0);

  const paymentData = (summary?.payment_status || []).map(p => ({
    name: p.status,
    value: p.count,
    fill: PAYMENT_STATUS_COLORS[p.status] || '#64748b',
  }));

  const tableCountData = Object.entries(summary?.table_counts || {}).map(([k, v]) => ({
    name: k.replace(/_/g, ' '),
    count: v,
  }));

  const dbOk = health?.database?.ok === true;
  const reconOk = !!health?.models?.reconciliation_schema;
  const excOk = !!health?.models?.exception_schema;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Dashboard</h1>
          <p>Live reconciliation overview · Real data from PostgreSQL</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          {lastRefreshed && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Updated {lastRefreshed.toLocaleTimeString()}
            </span>
          )}
          <button className="btn btn-secondary btn-sm" onClick={fetchData} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'animate-pulse' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 'var(--space-xl)' }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !summary && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 'var(--space-xl)', color: 'var(--text-muted)' }}>
          <div className="spinner spinner-lg" />
          <span>Loading reconciliation data…</span>
        </div>
      )}

      {/* KPI Cards */}
      {summary && (
        <>
          <div className="stats-grid">
            <KpiCard
              label="Total Bank Records"
              value={total.toLocaleString()}
              subtitle={`${summary.table_counts?.bank_records || 0} records in DB`}
              icon={Database}
              colorClass="indigo"
            />
            <KpiCard
              label="Reconciled"
              value={reconciled.toLocaleString()}
              subtitle="Matched to settlements"
              icon={CheckCircle2}
              colorClass="green"
              onClick={() => navigate('/reconciliation')}
            />
            <KpiCard
              label="Unreconciled"
              value={unreconciled.toLocaleString()}
              subtitle="Awaiting match"
              icon={AlertCircle}
              colorClass="rose"
            />
            <KpiCard
              label="Reconciliation Rate"
              value={`${rate.toFixed(2)}%`}
              subtitle={`${reconciled} of ${total} records matched`}
              icon={TrendingUp}
              colorClass="blue"
            />
            <KpiCard
              label="Total Discrepancy"
              value={formatINRShort(discrepancy)}
              subtitle="Unreconciled CREDIT amounts"
              icon={IndianRupee}
              colorClass="amber"
            />
            <KpiCard
              label="Total Settlements"
              value={(summary.settlements?.count || 0).toLocaleString()}
              subtitle={formatINRShort(summary.settlements?.net_amount)}
              icon={Layers}
              colorClass="cyan"
            />
          </div>

          {/* Charts row */}
          <div className="grid-2" style={{ marginBottom: 'var(--space-xl)' }}>
            {/* Reconciliation Status Pie */}
            <div className="card">
              <SectionHeader
                title="Reconciliation Status"
                subtitle="Bank records vs. settlements — from PostgreSQL"
              />
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={3}
                      dataKey="value"
                      nameKey="name"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
                      labelLine={false}
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-normal)', borderRadius: 8, fontSize: 12 }}
                      formatter={(v) => [v.toLocaleString(), 'Records']}
                    />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state" style={{ padding: 'var(--space-xl) 0' }}>No data</div>
              )}
            </div>

            {/* Category breakdown */}
            <div className="card">
              <SectionHeader
                title="Bank Record Categories"
                subtitle="Transaction categories in bank records"
              />
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={categoryData} layout="vertical" margin={{ left: 10 }}>
                  <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={120}
                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-normal)', borderRadius: 8, fontSize: 12 }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {categoryData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Payment status + Database record counts */}
          <div className="grid-2" style={{ marginBottom: 'var(--space-xl)' }}>
            {/* Payment status */}
            <div className="card">
              <SectionHeader
                title="Payment Status Breakdown"
                subtitle={`${summary.table_counts?.payments || 0} total payments`}
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                {paymentData.map(({ name, value, fill }) => {
                  const totalPay = paymentData.reduce((s, d) => s + d.value, 0);
                  const pct = totalPay ? ((value / totalPay) * 100).toFixed(1) : 0;
                  return (
                    <div key={name}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                        <span style={{ color: 'var(--text-secondary)' }}>{name}</span>
                        <span style={{ fontWeight: 700, color: fill }}>{value.toLocaleString()} ({pct}%)</span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${pct}%`, background: fill }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Table record counts */}
            <div className="card">
              <SectionHeader
                title="Database Record Counts"
                subtitle="Total records in each operational table"
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {tableCountData.map(({ name, count }) => (
                  <div key={name} style={{
                    display: 'flex', justifyContent: 'space-between', padding: '8px 0',
                    borderBottom: '1px solid var(--border-subtle)', fontSize: 13,
                  }}>
                    <span style={{ color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{name}</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {count.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recent Records */}
          {summary.recent_records?.length > 0 && (
            <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
                <SectionHeader title="Recent Bank Records" subtitle="Latest transactions from PostgreSQL" />
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => navigate('/transactions')}
                >
                  View All <ArrowRight size={14} />
                </button>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Record ID</th>
                      <th>Merchant</th>
                      <th>Date</th>
                      <th>Amount</th>
                      <th>Type</th>
                      <th>Category</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.recent_records.map(r => (
                      <tr key={r.id} style={{ cursor: 'pointer' }} onClick={() => navigate('/reconciliation')}>
                        <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{r.id}</td>
                        <td style={{ fontSize: 12 }}>{r.merchant_id}</td>
                        <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.date}</td>
                        <td style={{ fontWeight: 600 }}>{formatINR(r.amount)}</td>
                        <td>
                          <span className={`badge ${r.type === 'CREDIT' ? 'badge-matched' : 'badge-pending'}`}>
                            {r.type}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                          {r.category?.replace(/_/g, ' ')}
                        </td>
                        <td>
                          <span className={`badge ${r.reconciled ? 'badge-matched' : 'badge-unmatched'}`}>
                            {r.reconciled ? 'RECONCILED' : 'UNMATCHED'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* System status */}
          <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
            <SectionHeader title="Live System Status" subtitle="Real-time backend component health" />
            <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
              {[
                { label: 'PostgreSQL',         ok: dbOk,    icon: '🗄️' },
                { label: 'Reconciliation ML',  ok: reconOk, icon: '🤖' },
                { label: 'Exception Classifier', ok: excOk, icon: '🧠' },
                { label: 'Backend API',        ok: !!health, icon: '🌐' },
              ].map(({ label, ok, icon }) => (
                <div key={label} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'var(--bg-elevated)', padding: '10px 16px',
                  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)',
                  fontSize: 13, minWidth: 170,
                }}>
                  <span>{icon}</span>
                  <div className={`status-dot ${ok ? 'ok' : 'error'}`} />
                  <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                  <span style={{
                    marginLeft: 'auto', fontWeight: 600, fontSize: 12,
                    color: ok ? 'var(--status-matched)' : 'var(--status-unmatched)',
                  }}>
                    {ok ? 'Online' : 'Offline'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div>
            <h3 style={{ fontSize: 15, marginBottom: 'var(--space-md)' }}>Quick Actions</h3>
            <div className="grid-2">
              {[
                { label: 'Run Reconciliation',  desc: 'Match a bank record to settlements',  path: '/reconciliation', color: 'blue' },
                { label: 'Upload Data',          desc: 'Ingest CSV, XLSX, or PDF files',      path: '/upload',         color: 'indigo' },
                { label: 'Ask the AI',           desc: 'Chat with Gemini · RAG · Tool-use',   path: '/chat',           color: 'cyan' },
                { label: 'Lookup Transaction',   desc: 'Fetch a payment, order, or settlement', path: '/transactions', color: 'green' },
              ].map(({ label, desc, path, color }) => (
                <div
                  key={path}
                  className={`stat-card ${color}`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(path)}
                >
                  <div className="stat-body">
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                      {label}
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{desc}</div>
                  </div>
                  <ArrowRight size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Footer note */}
      <div style={{ textAlign: 'center', marginTop: 'var(--space-2xl)', color: 'var(--text-muted)', fontSize: 12 }}>
        Powered by Gemini · RAG · Logistic Regression ML · PostgreSQL — All figures from live database
      </div>
    </div>
  );
}
