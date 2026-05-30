import React from 'react';

export default function OccupancyGauge({ current, capacity }) {
  const percentage = Math.min(100, Math.max(0, (current / capacity) * 100)) || 0;
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  let statusColor = '#10b981'; // Green
  let statusText = 'Normal';
  if (percentage >= 85) {
    statusColor = '#ef4444'; // Red
    statusText = 'Overcrowded';
  } else if (percentage >= 60) {
    statusColor = '#f59e0b'; // Yellow
    statusText = 'Busy';
  }

  return (
    <div className="occupancy-gauge-container">
      <div className="gauge-wrapper">
        <svg className="gauge-svg" viewBox="0 0 140 140">
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
          </defs>
          <circle
            className="gauge-bg"
            cx="70"
            cy="70"
            r={radius}
            strokeWidth="12"
            fill="none"
          />
          <circle
            className="gauge-fill"
            cx="70"
            cy="70"
            r={radius}
            strokeWidth="12"
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
          />
        </svg>
        <div className="gauge-content">
          <span className="gauge-value">{current}</span>
          <span className="gauge-capacity">/ {capacity}</span>
        </div>
      </div>
      <div className="gauge-status">
        <span
          className={`status-dot ${percentage >= 85 ? 'pulse' : ''}`}
          style={{ backgroundColor: statusColor }}
        ></span>
        <span style={{ color: statusColor }}>{statusText} ({Math.round(percentage)}%)</span>
      </div>
    </div>
  );
}
