import React, { useState, useEffect } from 'react';
import { LayoutDashboard, Activity, Camera, AlertTriangle } from 'lucide-react';

export default function Layout({ children }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h2>StoreIQ</h2>
          <div className="ai-badge">
            <span className="pulse-dot"></span> AI Powered
          </div>
        </div>
        <nav className="sidebar-nav">
          <a href="#" className="nav-item active">
            <LayoutDashboard size={20} /> Dashboard
          </a>
          <a href="#" className="nav-item">
            <Activity size={20} /> Live Feed
          </a>
          <a href="#" className="nav-item">
            <Camera size={20} /> Cameras
          </a>
          <a href="#" className="nav-item">
            <AlertTriangle size={20} /> Anomalies
          </a>
        </nav>
      </aside>
      <main className="main-content">
        <header className="dashboard-header">
          <h1>Store Intelligence</h1>
          <div className="header-time">{time.toLocaleString()}</div>
        </header>
        <div className="dashboard-content">
          {children}
        </div>
      </main>
    </div>
  );
}
