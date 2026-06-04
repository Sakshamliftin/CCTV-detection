# Store Intelligence v1.1 - Architectural Choices

This document outlines three key architectural decisions made during the v1.1 upgrade, structured as required by the challenge scoring criteria.

## 1. Detection Model Selection
*   **Options Considered:** (A) YOLOv8 + DeepSORT for real-time tracking, (B) YOLOv9 for higher accuracy with BoT-SORT, (C) Vision-Language Models (VLMs) like GPT-4V for zero-shot zone and staff classification.
*   **What AI Suggested:** The LLM suggested YOLOv8 + DeepSORT because it is well-supported, extremely fast, and adequate for basic retail analytics. It also proposed using an LLM periodically to classify staff uniforms.
*   **What I Chose and Why:** I selected **YOLOv8 + ByteTrack** (via the `supervision` library). ByteTrack provides excellent re-identification by keeping low-confidence boxes around, which solves the "partial occlusion" challenge in crowded billing lines better than DeepSORT. For staff exclusion, rather than a slow/expensive VLM, I chose a deterministic heuristic (`track_id % 10 == 0`) for the challenge, but the system is designed to take a boolean `is_staff` flag natively from any future classifier.

## 2. Event Schema Design Rationale
*   **Options Considered:** (A) A flat event log with dozens of nullable columns, (B) A hierarchical document-style schema (e.g., storing the entire trajectory history inside the event), (C) A normalized, flat state-transition schema with an extensible `metadata` JSON blob.
*   **What AI Suggested:** The AI initially suggested a deeply nested JSON structure grouping events by visitor, which would mean emitting one massive payload per customer at the end of their session.
*   **What I Chose and Why:** I chose the **Normalized State-Transition Schema** (Option C). A streaming analytics system needs granular, real-time events (`person_entered`, `zone_entered`, `dwell_time_completed`) to compute metrics on the fly (e.g., live queue depth). Emitting only at the end of a session would make real-time dashboards impossible. The `metadata` JSON blob allows for schema evolution (e.g., adding `queue_depth` or `group_id`) without requiring database migrations.

## 3. API Architecture (Idempotency and Stateful Analytics)
*   **Options Considered:** (A) Completely stateless API backed by complex SQL aggregations on every request, (B) Stateful in-memory metrics with Kafka as the source of truth, (C) Redis-backed session state.
*   **What AI Suggested:** The AI strongly advocated for Redis to handle visitor sessions and idempotency across multiple API instances.
*   **What I Chose and Why:** I chose **Stateful In-Memory Analytics with PostgreSQL Backing** (Option B). While Redis is the industry standard for this, adding another infrastructure dependency (Redis container) would violate the simplicity of the deployment. By maintaining a `SessionState` graph in Python memory (inside `AnalyticsEngine`) and using PostgreSQL's primary keys (`event_id`) to silently reject cross-process duplicates, I achieved idempotent, high-performance funnel tracking without the operational overhead of a distributed cache.
