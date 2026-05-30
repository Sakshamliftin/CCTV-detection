import React from 'react';

export default function MetricCard({ title, value, subtitle, icon: Icon, trend, color }) {
  return (
    <div className="metric-card glass-panel" style={{ '--card-color': color }}>
      <div className="metric-card-header">
        <h3 className="metric-title">{title}</h3>
        <div className="metric-icon" style={{ backgroundColor: `${color}20`, color: color }}>
          <Icon size={20} />
        </div>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-footer">
        {trend !== undefined && (
          <span className={`metric-trend ${trend > 0 ? 'positive' : trend < 0 ? 'negative' : 'neutral'}`}>
            {trend > 0 ? '▲' : trend < 0 ? '▼' : '—'} {Math.abs(trend)}%
          </span>
        )}
        <span className="metric-subtitle">{subtitle}</span>
      </div>
    </div>
  );
}
