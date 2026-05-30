import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function VisitorChart({ data }) {
  const formatTime = (isoString) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: 'numeric', hour12: true });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="custom-tooltip glass-panel">
          <p className="tooltip-label">{formatTime(label)}</p>
          <p className="tooltip-data" style={{ color: '#06b6d4' }}>
            Visitors: <span className="bold">{payload[0].value}</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-card glass-panel span-2-cols">
      <div className="card-header">
        <h3>Visitor Traffic (24h)</h3>
      </div>
      <div className="chart-container" style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorVisitors" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.8}/>
                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <XAxis dataKey="timestamp" tickFormatter={formatTime} stroke="#4b5563" tick={{fill: '#9ca3af'}} />
            <YAxis stroke="#4b5563" tick={{fill: '#9ca3af'}} />
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="visitors" stroke="#06b6d4" strokeWidth={3} fillOpacity={1} fill="url(#colorVisitors)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
