import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  GitMerge,
  MessageSquare,
  Activity,
  Database,
  Upload,
  Zap,
} from 'lucide-react';

const navItems = [
  { to: '/',               label: 'Dashboard',    icon: LayoutDashboard, end: true },
  { to: '/reconciliation', label: 'Reconciliation', icon: GitMerge },
  { to: '/transactions',   label: 'Transactions', icon: Database },
  { to: '/upload',         label: 'Upload Data',  icon: Upload },
  { to: '/chat',           label: 'AI Chat',      icon: MessageSquare },
  { to: '/health',         label: 'System Health',icon: Activity },
];

export default function Sidebar({ systemStatus }) {
  const statusColor =
    systemStatus === 'ok' ? 'ok' : systemStatus === 'degraded' ? 'pending' : 'error';

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="logo-icon">
          <Zap size={18} color="#fff" />
        </div>
        <div className="logo-text">
          Razorpay AI
          <span>Finance Controller</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="nav-section-label">Main</div>
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer status */}
      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
          <div className={`status-dot ${statusColor}`} />
          Backend {systemStatus ?? 'checking…'}
        </div>
        <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)', opacity: 0.6 }}>
          gemini-3.1-flash-lite · RAG enabled
        </div>
      </div>
    </aside>
  );
}
