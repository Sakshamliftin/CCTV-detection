import React, { useState } from 'react';

export default function StoreHeatmap({ zones }) {
  const [hoveredZone, setHoveredZone] = useState(null);

  // Store layout geometry
  const layout = {
    zone_entrance: { x: 250, y: 380, w: 300, h: 100 },
    zone_checkout: { x: 580, y: 380, w: 200, h: 100 },
    zone_electronics: { x: 20, y: 20, w: 370, h: 170 },
    zone_grocery: { x: 410, y: 20, w: 370, h: 170 },
    zone_clothing: { x: 20, y: 210, w: 370, h: 150 },
  };

  // Find max occupancy for normalization (at least 1 to avoid div by zero)
  const maxOccupancy = Math.max(1, ...(zones || []).map(z => z.current_occupancy || 0));

  const getZoneOpacity = (occupancy) => {
    if (!occupancy) return 0.15;
    const normalized = occupancy / maxOccupancy;
    return 0.15 + (normalized * 0.7); // scale between 0.15 and 0.85
  };

  return (
    <div className="heatmap-card glass-panel span-2-cols">
      <div className="card-header">
        <h3>Store Heatmap</h3>
      </div>
      <div className="heatmap-container">
        <svg className="heatmap-svg" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid meet">
          {/* Background grid */}
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1"/>
            </pattern>
          </defs>
          <rect width="800" height="500" fill="url(#grid)" />
          
          {/* Store Boundary */}
          <rect x="10" y="10" width="780" height="480" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2" strokeDasharray="10 5" />
          
          {/* Entrances indicator */}
          <path d="M 350 490 L 450 490" stroke="#06b6d4" strokeWidth="4" />
          <text x="400" y="485" fill="#9ca3af" fontSize="12" textAnchor="middle">MAIN ENTRANCE</text>

          {/* Zones */}
          {zones && zones.map(zone => {
            const geo = layout[zone.zone_id];
            if (!geo) return null;
            
            const isHovered = hoveredZone === zone.zone_id;
            const opacity = isHovered ? Math.min(1, getZoneOpacity(zone.current_occupancy) + 0.2) : getZoneOpacity(zone.current_occupancy);
            
            return (
              <g 
                key={zone.zone_id} 
                className="heatmap-zone-group"
                onMouseEnter={() => setHoveredZone(zone.zone_id)}
                onMouseLeave={() => setHoveredZone(null)}
                style={{ cursor: 'pointer', transition: 'all 0.3s ease' }}
              >
                <rect
                  x={geo.x}
                  y={geo.y}
                  width={geo.w}
                  height={geo.h}
                  fill={zone.color || '#06b6d4'}
                  fillOpacity={opacity}
                  stroke={zone.color || '#06b6d4'}
                  strokeWidth={isHovered ? 3 : 1}
                  rx="4"
                  style={{ transition: 'fill-opacity 0.3s ease, stroke-width 0.3s' }}
                />
                
                <text x={geo.x + geo.w/2} y={geo.y + geo.h/2 - 10} fill="#fff" fontSize="16" fontWeight="600" textAnchor="middle" style={{ pointerEvents: 'none' }}>
                  {zone.zone_name}
                </text>
                
                <text x={geo.x + geo.w/2} y={geo.y + geo.h/2 + 15} fill="rgba(255,255,255,0.8)" fontSize="14" textAnchor="middle" style={{ pointerEvents: 'none' }}>
                  {zone.current_occupancy} people
                </text>
                
                {/* Wall styling (left side) */}
                <path d={`M ${geo.x} ${geo.y} L ${geo.x} ${geo.y + geo.h}`} stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay (HTML based for better styling) */}
        {hoveredZone && (
          <div className="heatmap-tooltip glass-panel">
            {(() => {
              const zone = zones.find(z => z.zone_id === hoveredZone);
              if (!zone) return null;
              return (
                <>
                  <h4 style={{ color: zone.color }}>{zone.zone_name}</h4>
                  <div className="tooltip-grid">
                    <div>
                      <span className="label">Occupancy:</span>
                      <span className="val bold">{zone.current_occupancy}</span>
                    </div>
                    <div>
                      <span className="label">Traffic:</span>
                      <span className="val">{zone.entries} in / {zone.exits} out</span>
                    </div>
                    <div>
                      <span className="label">Avg Dwell:</span>
                      <span className="val">{Math.round(zone.avg_dwell_seconds)}s</span>
                    </div>
                  </div>
                </>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
