-- cameras table
CREATE TABLE cameras (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    rtsp_url VARCHAR(500),
    zone_ids TEXT[], -- array of zone IDs covered
    status VARCHAR(20) DEFAULT 'offline',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- store_events: business-level events from vision pipeline
CREATE TABLE store_events (
    id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    camera_id VARCHAR(50) REFERENCES cameras(id),
    track_id INTEGER,
    zone_id VARCHAR(50),
    zone_name VARCHAR(100),
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_store_events_timestamp ON store_events(timestamp DESC);
CREATE INDEX idx_store_events_type ON store_events(event_type);
CREATE INDEX idx_store_events_zone ON store_events(zone_id);

-- anomaly_events
CREATE TABLE anomaly_events (
    id VARCHAR(100) PRIMARY KEY,
    anomaly_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- info, warning, critical
    zone_id VARCHAR(50),
    zone_name VARCHAR(100),
    description TEXT,
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_anomaly_events_timestamp ON anomaly_events(timestamp DESC);
CREATE INDEX idx_anomaly_events_severity ON anomaly_events(severity);

-- analytics_snapshots: periodic roll-ups
CREATE TABLE analytics_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    total_occupancy INTEGER DEFAULT 0,
    total_visitors INTEGER DEFAULT 0,
    avg_dwell_seconds FLOAT DEFAULT 0,
    peak_occupancy INTEGER DEFAULT 0,
    zone_occupancy JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_snapshots_timestamp ON analytics_snapshots(timestamp DESC);

-- zone_analytics: per-zone traffic stats
CREATE TABLE zone_analytics (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(50) NOT NULL,
    zone_name VARCHAR(100),
    hour_bucket TIMESTAMPTZ NOT NULL,
    entries INTEGER DEFAULT 0,
    exits INTEGER DEFAULT 0,
    avg_dwell_seconds FLOAT DEFAULT 0,
    peak_occupancy INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_zone_analytics_zone ON zone_analytics(zone_id);
CREATE INDEX idx_zone_analytics_hour ON zone_analytics(hour_bucket DESC);

-- Seed cameras from config
INSERT INTO cameras (id, name, location, rtsp_url, zone_ids, status) VALUES
('cam_01', 'Main Entrance Camera', 'Front Door', 'rtsp://localhost:8554/cam01', ARRAY['zone_entrance'], 'online'),
('cam_02', 'Checkout Area Camera', 'Checkout Counter', 'rtsp://localhost:8554/cam02', ARRAY['zone_checkout'], 'online'),
('cam_03', 'Floor Camera North', 'North Aisle', 'rtsp://localhost:8554/cam03', ARRAY['zone_electronics', 'zone_grocery'], 'online'),
('cam_04', 'Floor Camera South', 'South Aisle', 'rtsp://localhost:8554/cam04', ARRAY['zone_clothing'], 'online');
