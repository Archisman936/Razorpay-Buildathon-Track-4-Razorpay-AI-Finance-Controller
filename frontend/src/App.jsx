import { Routes, Route } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Reconciliation from './pages/Reconciliation.jsx';
import Chat from './pages/Chat.jsx';
import Health from './pages/Health.jsx';
import Transactions from './pages/Transactions.jsx';
import Upload from './pages/Upload.jsx';
import { healthApi } from './api.js';

export default function App() {
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    healthApi.get()
      .then(data => setSystemStatus(data?.status ?? 'unknown'))
      .catch(() => setSystemStatus('error'));
  }, []);

  return (
    <div className="app-layout">
      <Sidebar systemStatus={systemStatus} />
      <div className="main-content">
        <Routes>
          <Route path="/"               element={<Dashboard />} />
          <Route path="/reconciliation" element={<Reconciliation />} />
          <Route path="/transactions"   element={<Transactions />} />
          <Route path="/upload"         element={<Upload />} />
          <Route path="/chat"           element={<Chat />} />
          <Route path="/health"         element={<Health />} />
        </Routes>
      </div>
    </div>
  );
}
