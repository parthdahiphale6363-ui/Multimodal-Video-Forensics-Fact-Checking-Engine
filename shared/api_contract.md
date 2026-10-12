# API Contract

This document outlines the REST API surface for the video fact-checking system. All JSON requests and responses map directly to the Pydantic schemas defined in `shared/schemas/`.

## 1. Submit a Video Job

Submit a new video URL for the pipeline to process.

**Endpoint:** `POST /jobs`

**Request Body:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=example"
}
```

**Response:** Returns a `Job` object.
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "video_url": "https://www.youtube.com/watch?v=example",
  "status": "pending",
  "progress_percent": 0.0,
  "error_message": null,
  "claim_ids": [],
  "created_at": "2026-06-28T14:11:47Z",
  "updated_at": "2026-06-28T14:11:47Z"
}
```

---

## 2. Poll Job Status

Check the pipeline progress of an existing job.

**Endpoint:** `GET /jobs/{id}`

**Response:** Returns a `Job` object.
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "video_url": "https://www.youtube.com/watch?v=example",
  "status": "extracting_claims",
  "progress_percent": 60.5,
  "error_message": null,
  "claim_ids": [],
  "created_at": "2026-06-28T14:11:47Z",
  "updated_at": "2026-06-28T14:13:22Z"
}
```

---

## 3. Retrieve Job Claims and Verdicts

Fetch all claims extracted from a specific job and their corresponding verdicts (once verified).

**Endpoint:** `GET /jobs/{id}/claims`

**Response:** Returns a list of objects containing the `Claim` and its associated `Verdict`.
```json
[
  {
    "claim": {
      "id": "c23e4567-e89b-12d3-a456-426614174001",
      "source_video_id": "example",
      "source_platform": "youtube",
      "raw_text": "The economy completely collapsed yesterday.",
      "normalized_text": "The national economy completely collapsed on June 27, 2026.",
      "language": "en",
      "timestamp_in_video": 45.5,
      "embedding_id": "emb-12345",
      "created_at": "2026-06-28T14:14:00Z"
    },
    "verdict": {
      "id": "v23e4567-e89b-12d3-a456-426614174002",
      "claim_id": "c23e4567-e89b-12d3-a456-426614174001",
      "label": "false",
      "confidence": 0.95,
      "evidence": [
        {
          "source_url": "https://news.example.com/economy-stable",
          "source_title": "Economic Indicators Remain Stable",
          "snippet": "Despite online rumors, the stock market closed at an all-time high...",
          "relevance_score": 0.98
        }
      ],
      "reasoning": "Major economic indicators are positive and no major market crashes have occurred recently.",
      "created_at": "2026-06-28T14:14:30Z"
    }
  }
]
```

---

## 4. Find Related Claims Across Videos

Fetch semantically similar claims (potentially across different languages and platforms) from other videos to show cross-platform spread.

**Endpoint:** `GET /claims/{id}/related`

**Response:** Returns a list of `Claim` objects that belong to the same semantic cluster.
```json
[
  {
    "id": "c23e4567-e89b-12d3-a456-426614179999",
    "source_video_id": "insta_123",
    "source_platform": "instagram",
    "raw_text": "La economía se hundió totalmente.",
    "normalized_text": "La economía nacional se hundió totalmente el 27 de junio de 2026.",
    "language": "es",
    "timestamp_in_video": 12.0,
    "embedding_id": "emb-98765",
    "created_at": "2026-06-27T10:00:00Z"
  }
]
```
