import React from 'react';
import { Users, Clock, TrendingUp, Activity, RefreshCw } from 'lucide-react';
import Layout from './components/Layout';
import MetricCard from './components/MetricCard';
import OccupancyGauge from './components/OccupancyGauge';
import VisitorChart from './components/VisitorChart';
import ZoneTrafficChart from './components/ZoneTrafficChart';
import EventFeed from './components/EventFeed';
import AnomalyFeed from './components/AnomalyFeed';
import StoreHeatmap from './components/StoreHeatmap';
import { api } from './api/client';
import { usePolling } from './hooks/usePolling';

function App() {
  // Data hooks with polling
  const { data: occData, loading: occLoading, error: occError } = usePolling(api.getOccupancy, 5000);
  const { data: sumData, loading: sumLoading } = usePolling(api.getSummary, 10000);
  const { data: histData } = usePolling(() => api.getHistorical(24), 60000);
  const { data: zoneData } = usePolling(api.getZoneTraffic, 10000);
  const { data: eventsData } = usePolling(() => api.getRecentEvents(50), 3000);
  const { data: anomaliesData } = usePolling(() => api.getAnomalies(20), 5000);

  const formatDwellTime = (seconds) => {
    if (!seconds) return '0m 0s';
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  };

  const loading = occLoading || sumLoading;

  if (loading && !occData) {
    return (
      <Layout>
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Initializing Store Intelligence...</p>
        </div>
      </Layout>
    );
  }

  if (occError) {
    return (
      <Layout>
        <div className="error-state glass-panel">
          <AlertTriangle size={48} color="#ef4444" />
          <h2>Connection Error</h2>
          <p>{occError}</p>
          <button className="retry-btn" onClick={() => window.location.reload()}>
            <RefreshCw size={16} /> Retry
          </button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="dashboard-grid">
        {/* ROW 1: Metrics */}
        <div className="metric-card glass-panel" style={{ '--card-color': '#06b6d4' }}>
          <div className="metric-card-header">
            <h3 className="metric-title">Store Occupancy</h3>
            <div className="metric-icon" style={{ backgroundColor: '#06b6d420', color: '#06b6d4' }}>
              <Users size={20} />
            </div>
          </div>
          <div className="gauge-container-wrapper" style={{ marginTop: '10px' }}>
             <OccupancyGauge current={occData?.total_occupancy || 0} capacity={occData?.capacity || 200} />
          </div>
        </div>

        <MetricCard 
          title="Total Visitors Today" 
          value={(sumData?.total_visitors || 0).toLocaleString()} 
          subtitle="Unique individuals tracked"
          icon={Activity} 
          trend={12} 
          color="#8b5cf6" 
        />
        
        <MetricCard 
          title="Avg Dwell Time" 
          value={formatDwellTime(sumData?.avg_dwell_seconds || 0)} 
          subtitle="Across all zones"
          icon={Clock} 
          color="#10b981" 
        />
        
        <MetricCard 
          title="Peak Occupancy" 
          value={sumData?.peak_occupancy || 0} 
          subtitle="Highest concurrent today"
          icon={TrendingUp} 
          trend={-5} 
          color="#f59e0b" 
        />

        {/* ROW 2: Charts & Heatmap */}
        <VisitorChart data={histData?.data || []} />
        <StoreHeatmap zones={zoneData?.zones || []} />

        {/* ROW 3: Zone Traffic */}
        <ZoneTrafficChart data={zoneData?.zones || []} />

        {/* ROW 4: Feeds */}
        <EventFeed events={eventsData?.events || []} />
        <AnomalyFeed anomalies={anomaliesData?.anomalies || []} />
      </div>
    </Layout>
  );
}

export default App;
