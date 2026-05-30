# CCTV Store Intelligence System

A real-time retail analytics pipeline built for the Purplle Tech Challenge 2026.

The system processes raw CCTV footage, detects and tracks visitors, generates structured behavioral events, and exposes live store intelligence through a FastAPI-based analytics service.

## Features

* Visitor detection and tracking
* Entry / Exit recognition
* Zone-based movement analytics
* Session-level visitor identification
* Real-time event ingestion
* Conversion funnel analytics
* Store heatmaps
* Queue monitoring and anomaly detection
* Health monitoring endpoints
* Dockerized deployment

## Tech Stack

* Python
* FastAPI
* OpenCV
* YOLO
* Tracking/Re-ID Pipeline
* SQLite/PostgreSQL (configurable)
* Docker & Docker Compose

---

## Project Structure

```bash
store-intelligence/
├── pipeline/
├── app/
├── tests/
├── docs/
├── docker-compose.yml
└── README.md
```

---

## Quick Start

Clone the repository:

```bash
git clone https://github.com/Sakshamliftin/CCTV-detection.git
cd CCTV-detection
```

Start the entire system:

```bash
docker compose up --build
```

API will be available at:

```bash
http://localhost:8000
```

Swagger docs:

```bash
http://localhost:8000/docs
```

---

## Running the Detection Pipeline

Place the challenge dataset inside:

```bash
data/
```

Run detection:

```bash
python pipeline/detect.py
```

Generated events are emitted in JSON format and can be directly ingested by the API.

---

## Event Ingestion

```bash
POST /events/ingest
```

The endpoint validates, deduplicates and stores incoming events.

Supported batch size:

```bash
Up to 500 events/request
```

---

## Available Endpoints

### Store Metrics

```bash
GET /stores/{id}/metrics
```

Returns:

* Unique visitors
* Conversion rate
* Average dwell time
* Queue depth
* Abandonment rate

### Funnel Analytics

```bash
GET /stores/{id}/funnel
```

Tracks:

```text
Entry → Zone Visit → Billing → Purchase
```

### Heatmap Data

```bash
GET /stores/{id}/heatmap
```

Returns zone popularity and normalized dwell scores.

### Anomaly Detection

```bash
GET /stores/{id}/anomalies
```

Detects:

* Queue spikes
* Conversion drops
* Dead zones
* Stale feeds

### Health Check

```bash
GET /health
```

Provides service health and latest ingestion status.

---

## Testing

Run all tests:

```bash
pytest
```

Coverage:

```bash
pytest --cov
```

The test suite covers ingestion, metrics, anomaly detection, idempotency and edge cases such as empty stores, re-entry sessions and zero-purchase scenarios.

---

## Design Philosophy

The goal was not to build a perfect computer vision system, but a production-oriented analytics pipeline that can operate under real retail constraints.

Special attention was given to:

* Re-entry handling
* Staff exclusion
* Session consistency
* Confidence-aware detections
* Idempotent ingestion
* Operational observability

The North Star metric throughout development was:

```text
Offline Store Conversion Rate
```

Every major design decision was evaluated based on whether it improved the accuracy or usefulness of that metric.

---

## Documentation

Additional implementation details can be found in:

```bash
docs/DESIGN.md
docs/CHOICES.md
```

These documents include architecture decisions, AI-assisted workflows, tradeoff analysis and model selection rationale.

---

Built for Purplle Tech Challenge 2026.
