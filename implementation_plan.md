# Multimodal Video Forensics & OSINT Engine — Implementation Plan

## Overview

Upgrade the existing **Video Fact-Checker** (currently a claim-extractor + DuckDuckGo verifier) into a full-blown **Multimodal Video Forensics & OSINT Engine** with:
- Data Mining module (classification, clustering, outlier detection, association rules, pattern mining)
- Extended OSINT collection (reverse image/geolocation/news/social/weather/timestamp)
- Deepfake + manipulation detection layer (heuristic-based, no GPU needed)
- Explainable AI reports (confidence heatmap, evidence timeline, manipulated region indicators)
- Stunning redesigned UI/UX with forensics-grade dashboard

The backend is FastAPI + Python. The frontend is Next.js (React/TSX).

---

## Proposed Changes

### 1. Backend — New Data Mining & Forensics Module

#### [NEW] `backend/services/data_mining.py`
Implements:
- **Data Cleaning**: remove duplicate evidence, normalize scores
- **Classification**: rule-based Real/Fake/Misleading/Deepfake/Unverified using multi-signal scoring
- **Clustering**: group similar evidence items by topic using TF-IDF cosine similarity (no heavy ML)
- **Outlier Detection**: flag anomalous confidence scores, detect suspicious metadata
- **Association Rules**: find relationships between claim verdicts (e.g., false claims co-occurring)
- **Pattern Mining**: detect temporal and thematic patterns in extracted claims
- **Similarity Analysis**: fuzzy-match claims against known misinformation patterns

#### [NEW] `backend/services/forensics.py`
Implements:
- **Metadata Analysis**: extract and analyze video URL metadata (platform, upload date heuristics)
- **Deepfake Heuristics**: LLM-guided analysis of transcript inconsistencies + contextual red flags
- **Voice Clone Detection**: heuristic detection via transcript cadence + claim-context mismatch
- **Scene Consistency**: temporal claim consistency analysis across transcript segments
- **Lip-sync / manipulation hints**: LLM analysis of transcript language patterns
- **Geolocation clues**: extract location references from transcript using NLP

#### [NEW] `backend/services/osint.py`
Implements:
- **Reverse Image/Video Search hints**: construct search queries targeting known platforms
- **News Verification**: DuckDuckGo news search for the video's claims
- **Social Media Verification**: search Twitter/Reddit for the claim topic
- **Geolocation Verification**: extract + verify geographic claims via web search
- **Timestamp Verification**: detect date/time inconsistencies in claims
- **Weather Verification**: cross-reference weather-related claims

#### [MODIFY] `backend/services/job_service.py`
- Integrate `data_mining.py` and `forensics.py` modules into the pipeline
- Add new pipeline stages: `forensics_analysis`, `osint_collection`, `data_mining`
- Update `compute_overall_verdict` to use multi-modal scoring (video+audio+metadata+osint+dm scores)
- Add `dm_report`, `forensics_report`, `osint_report` to job state

#### [MODIFY] `backend/routers/jobs.py`
- Add `/jobs/{job_id}/forensics` endpoint
- Add `/jobs/{job_id}/osint` endpoint
- Add `/jobs/{job_id}/dm_report` endpoint

#### [MODIFY] `backend/main.py`
- Register new routers/endpoints

---

### 2. Shared Schemas

#### [MODIFY] `shared/schemas/job.py`
- Add new `JobStatus` values: `forensics_analysis`, `osint_collection`, `data_mining`
- Add fields: `dm_report`, `forensics_report`, `osint_report`, `final_verdict_category`

---

### 3. Frontend — Complete UI Overhaul

#### [MODIFY] `frontend/src/app/globals.css`
Full redesign with:
- Forensics-themed dark UI (deep navy/teal/cyan palette)
- Glass morphism cards with neon glow effects
- Animated data flow visualization
- Radar chart-style score displays
- Timeline visualization for evidence
- Heatmap-style confidence displays
- Responsive grid layout with sidebar nav

#### [MODIFY] `frontend/src/app/page.tsx`
Complete rebuild with new sections:
1. **Hero Input** — dramatic forensics-themed URL submission
2. **Live Pipeline Visualizer** — animated 8-stage pipeline (vs current 4-stage)
3. **Forensics Dashboard** (new results view):
   - **Overall Verdict Card** — Genuine/Deepfake/Edited/Misleading/Fake with big confidence dial
   - **Multi-modal Score Panel** — video/audio/metadata/osint/dm scores as gauge meters
   - **Data Mining Report Panel** — classification, clusters, outliers, patterns
   - **OSINT Evidence Panel** — news/social/geolocation/timestamp/weather results
   - **AI Forensics Panel** — deepfake/voice-clone/manipulation analysis
   - **Claim Analysis Panel** — enhanced existing claim cards
   - **Explainable AI Panel** — confidence timeline, red flags highlighted
   - **Evidence Timeline** — chronological evidence flow

#### [NEW] `frontend/src/app/components/ForensicsDashboard.tsx`
New modular component file for dashboard panels

---

## New Pipeline Stages (8 total)

```
extracting → transcribing → extracting_claims → forensics_analysis → osint_collection → data_mining → verifying → done
```

---

## Key Design Decisions

> [!IMPORTANT]
> **No GPU/heavy ML required**: All AI analysis uses Groq LLM (already configured) for reasoning, and heuristic/rule-based algorithms for data mining. This keeps it fully runnable on your existing setup.

> [!NOTE]
> **Deepfake detection is LLM-heuristic**: We use Groq to analyze transcript patterns, language consistency, and contextual red flags — not vision models. This gives meaningful results without requiring model downloads.

> [!NOTE]
> **Data Mining is lightweight Python**: Using cosine similarity (numpy/sklearn if available, else pure Python fallback), frequency analysis, and rule-based pattern detection — no heavy dependencies added.

## Verification Plan

### Automated
- Start backend: `python backend/main.py`
- Start frontend: `npm run dev` inside `frontend/`
- Submit a YouTube URL and verify all 8 pipeline stages complete
- Verify new endpoints `/forensics`, `/osint`, `/dm_report` return data
- Verify UI shows all new panels

### Manual UI Verification
- Check forensics dashboard renders all panels
- Check multi-modal score gauges display
- Check evidence timeline renders
- Check responsive layout on narrow screen
