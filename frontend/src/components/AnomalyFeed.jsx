import React from 'react';
import { AlertTriangle, AlertCircle, Info, CheckCircle } from 'lucide-react';

export default function AnomalyFeed({ anomalies }) {
  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return '';
    const seconds = Math.floor((new Date() - new Date(timestamp)) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  const getSeverityStyle = (severity) => {
    switch (severity) {
      case 'critical': return { color: '#ef4444', Icon: AlertTriangle, glow: true };
      case 'warning': return { color: '#f59e0b', Icon: AlertCircle, glow: false };
      case 'info': return { color: '#3b82f6', Icon: Info, glow: false };
      default: return { color: '#9ca3af', Icon: Info, glow: false };
    }
  };

  const formatType = (type) => {
    return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  return (
    <div className="feed-card glass-panel">
      <div className="card-header">
        <h3>Anomaly Alerts</h3>
      </div>
      <div className="feed-content anomaly-feed">
        {anomalies && anomalies.length > 0 ? (
          anomalies.map((anomaly, index) => {
            const style = getSeverityStyle(anomaly.severity);
            const { Icon } = style;
            return (
              <div 
                key={anomaly.anomaly_id || index} 
                className={`anomaly-item fade-in-up ${style.glow ? 'critical-glow' : ''}`}
                style={{ borderLeftColor: style.color, animationDelay: `${index * 0.05}s` }}
              >
                <div className="anomaly-icon" style={{ color: style.color }}>
                  <Icon size={20} />
                </div>
                <div className="anomaly-details">
                  <div className="anomaly-header">
                    <span className="anomaly-type">{formatType(anomaly.anomaly_type)}</span>
                    <span className="anomaly-time">{formatTimeAgo(anomaly.timestamp)}</span>
                  </div>
                  <div className="anomaly-zone">{anomaly.zone_name}</div>
                  <div className="anomaly-desc">{anomaly.description}</div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="empty-state success">
            <CheckCircle size={32} color="#10b981" />
            <p>All clear — no anomalies detected</p>
          </div>
        )}
      </div>
    </div>
  );
}
