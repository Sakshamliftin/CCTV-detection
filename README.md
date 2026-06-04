# Store Intelligence API

Store Intelligence API is the central analytics brain that ingests structured events from edge CCTV feeds and exposes real-time business metrics and anomaly alerts.

## Quickstart

Get the system up and running in just 5 commands:

```bash
# 1. Clone the repository (if you haven't already)
# git clone <repository_url> && cd <repository>

# 2. Start the entire stack in the background
docker-compose up -d

# 3. Wait a few seconds for Kafka and PostgreSQL to initialize, then verify services are running
docker-compose ps

# 4. (Optional) Follow logs to watch the pipeline boot up
docker-compose logs -f backend

# 5. Check the system health endpoint (should return "status": "healthy")
curl http://localhost:8000/health
```

## Running the Detection Pipeline

The pipeline is designed to be fed by an edge CV service. You can run the detection pipeline manually against the provided CCTV clips to push events to the API.

To run the pipeline on the clips:
```bash
# Run the pipeline shell script provided in the challenge
# (Ensure you are in the python environment where your CV dependencies are installed)
cd pipeline
bash run.sh ../challenge-context/CCTV\ Footage-20260529T160731Z-3-00144614ea
```

*(Note: The above assumes you have implemented `run.sh` inside the `pipeline/` directory as suggested by the challenge layout. This executes `detect.py` which emits events to the local Kafka broker or directly to `POST /events/ingest`)*

## Live Endpoints

Once running, the API exposes the following endpoints (default port 8000):

*   **Ingest:** `POST /events/ingest`
*   **Metrics:** `GET /stores/{store_id}/metrics`
*   **Funnel:** `GET /stores/{store_id}/funnel`
*   **Heatmap:** `GET /stores/{store_id}/heatmap`
*   **Anomalies:** `GET /stores/{store_id}/anomalies`
*   **Health:** `GET /health`
