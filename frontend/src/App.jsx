import React, { useState } from 'react';
import { Users, Clock, TrendingUp, Activity, RefreshCw } from 'lucide-react';
import Layout from './components/Layout';
import MetricCard from './components/MetricCard';
import OccupancyGauge from './components/OccupancyGauge';
import VisitorChart from './components/VisitorChart';
import ZoneTrafficChart from './components/ZoneTrafficChart';
import EventFeed from './components/EventFeed';
import AnomalyFeed from './components/AnomalyFeed';
import StoreHeatmap from './components/StoreHeatmap';
import { StoreUpload, StoreSelector } from './components/StoreManager';
import { api } from './api/client';
import { usePolling } from './hooks/usePolling';

function App() {
  const [currentStore, setCurrentStore] = useState(null);

  // Data hooks with polling (only if currentStore is selected)
  const { data: occData, loading: occLoading, error: occError } = usePolling(
    () => currentStore ? api.getOccupancy(currentStore) : Promise.resolve(null), 5000
  );
  const { data: sumData, loading: sumLoading } = usePolling(
    () => currentStore ? api.getSummary(currentStore) : Promise.resolve(null), 10000
  );
  const { data: histData } = usePolling(
    () => currentStore ? api.getHistorical(currentStore, 24) : Promise.resolve(null), 60000
  );
  const { data: zoneData } = usePolling(
    () => currentStore ? api.getZoneTraffic(currentStore) : Promise.resolve(null), 10000
  );
  const { data: eventsData } = usePolling(
    () => api.getRecentEvents(50), 3000
  );
  const { data: anomaliesData } = usePolling(
    () => currentStore ? api.getAnomalies(currentStore, 20) : Promise.resolve(null), 5000
  );

  const formatDwellTime = (seconds) => {
    if (!seconds) return '0m 0s';
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  };

  return (
    <Layout>
      <div className="dashboard-grid">
        <StoreSelector currentStore={currentStore} onSelectStore={setCurrentStore} />
        <StoreUpload onStoreUploaded={setCurrentStore} />

        {currentStore && (
          <>
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
          </>
        )}
      </div>
    </Layout>
  );
}

export default App;
