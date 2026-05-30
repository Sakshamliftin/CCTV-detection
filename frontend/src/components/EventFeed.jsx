import React from 'react';

export default function EventFeed({ events }) {
  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return '';
    const seconds = Math.floor((new Date() - new Date(timestamp)) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  const getTypeStyle = (type) => {
    switch (type) {
      case 'person_entered': return { color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)', label: 'Entered' };
      case 'person_exited': return { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)', label: 'Exited' };
      case 'zone_entered': return { color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.15)', label: 'Zone In' };
      case 'zone_exited': return { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)', label: 'Zone Out' };
      case 'dwell_time_completed': return { color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)', label: 'Dwelled' };
      default: return { color: '#9ca3af', bg: 'rgba(156, 163, 175, 0.15)', label: type };
    }
  };

  return (
    <div className="feed-card glass-panel">
      <div className="card-header">
        <h3>Live Event Feed</h3>
        <span className="live-indicator"><span className="pulse-dot"></span> Live</span>
      </div>
      <div className="feed-content event-feed">
        {events && events.length > 0 ? (
          events.map((event, index) => {
            const style = getTypeStyle(event.event_type);
            return (
              <div key={event.event_id || index} className="feed-item fade-in-up" style={{ animationDelay: `${index * 0.05}s` }}>
                <div className="event-badge" style={{ color: style.color, backgroundColor: style.bg }}>
                  {style.label}
                </div>
                <div className="event-details">
                  <span className="event-zone">{event.zone_name}</span>
                  <span className="event-meta">Track {event.track_id} • {event.camera_id}</span>
                </div>
                <div className="event-time">{formatTimeAgo(event.timestamp)}</div>
              </div>
            );
          })
        ) : (
          <div className="empty-state">
            <p>No events yet</p>
          </div>
        )}
      </div>
    </div>
  );
}
