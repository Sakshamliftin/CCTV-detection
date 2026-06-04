# Store Intelligence v1.1 - System Design

Store Intelligence is an edge-to-cloud analytics platform designed to convert raw retail video feeds into structured business metrics, funnel analysis, and actionable anomaly alerts.

## High-Level Architecture

The system is composed of four main layers, orchestrated via `docker-compose`:

1.  **Vision Layer (`vision` service):**
    *   **Role:** Ingests video feeds (or simulations), runs object detection/tracking, and manages zone geometry.
    *   **Pipeline:** Uses OpenCV and pluggable detectors. For every frame, it extracts bounding boxes, correlates them across frames to maintain a stable `track_id`, and projects the center coordinates onto defined zone polygons.
    *   **Output:** Generates discrete state-transition events (e.g., `person_entered`, `zone_entered`, `dwell_time_completed`) and pushes them to Kafka.

2.  **Messaging Layer (Kafka):**
    *   **Role:** Provides durable, asynchronous decoupling between the edge computer vision workloads and the central backend processors.
    *   **Topics:** 
        *   `store_events`: High-volume stream of raw transition events.
        *   `anomaly_events`: Low-volume stream of flagged alerts requiring operational attention.

3.  **Backend Layer (`backend` service):**
    *   **Role:** Ingests events, computes stateful analytics, evaluates anomaly rules, and serves a RESTful API.
    *   **Analytics Engine:** Maintains an in-memory session graph (keyed by `visitor_id`) to compute funnels, dwell times, and occupancy. Periodically flushes snapshots to the database.
    *   **Anomaly Engine:** Passes events through a registry of detectors (`QueueSpikeDetector`, `ConversionDropDetector`, etc.) to trigger alerts.
    *   **API:** Built on FastAPI, exposing historical data and real-time metrics.

4.  **Storage Layer (PostgreSQL):**
    *   **Role:** Persists raw event logs, analytics snapshots, and anomaly records for historical querying and auditing.

## Event Schema (v1.1 standard)

All events emitted to Kafka conform to the following schema:

```json
{
  "event_id": "uuid-v4",
  "store_id": "store_01",
  "camera_id": "cam_01",
  "visitor_id": "visitor_1234",
  "event_type": "person_entered | person_exited | zone_entered | zone_exited | dwell_time_completed | purchase_completed",
  "timestamp": "ISO-8601 UTC string",
  "zone_id": "zone_entrance",
  "dwell_ms": 15000,
  "is_staff": false,
  "confidence": 0.92,
  "metadata": {
    "direction": "in",
    "group_id": "uuid-v4",
    "is_group": true
  }
}
```

## Key Flows

### 1. The Visitor Funnel
The visitor funnel represents the idealized journey of a shopper:
*   **Entry:** Triggered by `person_entered` into the store. A `SessionState` is opened.
*   **Zone Visit:** Triggered when the visitor enters any zone other than the entrance (e.g., `zone_grocery`).
*   **Billing Queue:** Triggered when the visitor enters `zone_checkout`.
*   **Purchase:** Triggered by a `purchase_completed` event.
*   **Exit:** Triggered by `person_exited`. The session is closed.
*   *Re-entry:* If a visitor exits and re-enters within `REENTRY_WINDOW_SEC` (300s), the same session is reopened to prevent inflating the unique visitor metric.

### 2. Anomaly Detection
Anomalies are detected by passing the event stream through registered `BaseDetector` instances.
*   **Stateful Checks:** Detectors like `QueueSpikeDetector` maintain their own rolling window history (e.g., 1-hour moving average of queue depth).
*   **Contextual Evaluation:** Detectors receive the current event, the current zone occupancy map, and calculated business metrics, allowing complex rules like "ConversionDrop" (which compares today's conversion rate to a baseline).

### 3. Idempotent Ingestion
Third-party clients can push historical or batched events via `POST /api/v1/events/ingest`.
*   The system first checks the `_seen_event_ids` memory cache for rapid deduplication.
*   It then attempts to insert the event into PostgreSQL. A primary key constraint on `id` ensures that even cross-process duplicates are rejected.
*   Only newly accepted events are forwarded to the Analytics Engine.

## Extensibility

*   **Adding Zones:** Define a new polygon in `infrastructure/config/store_zones.json`. The vision layer will automatically detect transitions, and the backend will allocate metrics.
*   **Adding Anomalies:** Create a new class inheriting from `BaseDetector` in `anomaly_engine.py` and add it to the `DetectorRegistry`.
*   **Adding Models:** Swap the implementation in `detector.py` or `tracker.py` to upgrade the underlying CV models without altering the pipeline architecture.

## AI-Assisted Decisions
1. **Schema Design (Agreed):** The AI suggested separating `event_type` from `metadata` so that the primary routing could be done without parsing the metadata JSON blob. I agreed and implemented this, ensuring core fields like `visitor_id` and `event_type` are top-level.
2. **Re-entry Window Duration (Overrode):** The AI suggested a 60-second window for re-entry logic. I overrode this and set it to 300 seconds (5 minutes), as real-world shoppers often take longer to answer a phone call or retrieve an item from their car.
3. **Database Selection (Overrode):** The AI suggested MongoDB for storing the flexible JSON event metadata. I overrode this and chose PostgreSQL using a `JSONB` column. This kept the architecture simple (no extra NoSQL dependency) while still allowing fast indexing on the metadata blob if needed later.
