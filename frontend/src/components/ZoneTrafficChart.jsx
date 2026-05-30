import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function ZoneTrafficChart({ data }) {
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="custom-tooltip glass-panel">
          <p className="tooltip-label bold">{label}</p>
          <p className="tooltip-data" style={{ color: payload[0].payload.color }}>
            Entries: <span className="bold">{payload[0].value}</span>
          </p>
          <p className="tooltip-data" style={{ color: payload[1].payload.color, opacity: 0.8 }}>
            Exits: <span className="bold">{payload[1].value}</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-card glass-panel span-2-cols">
      <div className="card-header">
        <h3>Zone Traffic</h3>
      </div>
      <div className="chart-container" style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
            <XAxis dataKey="zone_name" stroke="#4b5563" tick={{fill: '#9ca3af'}} />
            <YAxis stroke="#4b5563" tick={{fill: '#9ca3af'}} />
            <Tooltip content={<CustomTooltip />} cursor={{fill: '#1f2937', opacity: 0.4}} />
            <Bar dataKey="entries" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-entries-${index}`} fill={entry.color || '#06b6d4'} />
              ))}
            </Bar>
            <Bar dataKey="exits" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-exits-${index}`} fill={entry.color || '#06b6d4'} opacity={0.6} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
