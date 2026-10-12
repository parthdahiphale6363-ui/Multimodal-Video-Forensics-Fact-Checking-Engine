"""
export_service.py — Executive Forensic Dossier & Intelligence Brief Generator
Generates publication-ready Markdown and structured JSON intelligence dossiers
for completed video verification jobs.
"""

import hashlib
import json
import datetime
from typing import Dict, Any

def generate_markdown_dossier(
    job_id: str,
    video_url: str,
    overall_verdict: str,
    category: str,
    confidence: float,
    breakdown: Dict[str, Any],
    claims: list,
    forensics: Dict[str, Any] = None,
    osint: Dict[str, Any] = None,
    dm_report: Dict[str, Any] = None
) -> str:
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Generate cryptographic integrity hash for the dossier
    content_to_hash = f"{job_id}:{video_url}:{overall_verdict}:{confidence}:{len(claims)}"
    audit_hash = hashlib.sha256(content_to_hash.encode("utf-8")).hexdigest()[:16].upper()

    md = []
    md.append("# 🛡️ TruthLens AI — Executive Forensic Verification Dossier")
    md.append(f"**Verification Audit Hash:** `SHA256-{audit_hash}`  ")
    md.append(f"**Generated:** {now_utc}  ")
    md.append(f"**Target Media:** [{video_url}]({video_url})  ")
    md.append(f"**Audit Job ID:** `{job_id}`  \n")
    md.append("---")

    md.append("## 📊 Executive Summary & Final Verdict")
    md.append(f"- **Final Verdict Determination:** **{overall_verdict}**")
    md.append(f"- **Classification Category:** `{category}`")
    md.append(f"- **Calibrated Confidence Score:** **{confidence:.1f}%**")
    
    veto = breakdown.get("veto_applied")
    if veto:
        md.append(f"\n> ⚠️ **CONSTITUTIONAL VETO ENFORCED:** {veto.get('reason')} (Governor: `{veto.get('type')}`)")
        
    md.append("\n### Claim Breakdown Summary")
    md.append(f"| Metric | Value |")
    md.append(f"|---|---|")
    md.append(f"| Total Claims Analyzed | {breakdown.get('total', len(claims))} |")
    md.append(f"| Verified True | {breakdown.get('true', 0)} |")
    md.append(f"| Debunked False | {breakdown.get('false', 0)} |")
    md.append(f"| Misleading / Out of Context | {breakdown.get('misleading', 0)} |")
    md.append(f"| Unverifiable / Low Signal | {breakdown.get('unverifiable', 0)} |")

    # Forensics Section
    if forensics:
        md.append("\n---\n## 🔬 Deep Visual & Acoustic Forensics")
        deepfake_pct = round(forensics.get("deepfake_probability", 0) * 100)
        voice_pct = round(forensics.get("voice_clone_probability", 0) * 100)
        consistency_pct = round(forensics.get("scene_consistency_score", 0) * 100)
        
        md.append(f"- **Deepfake Manipulation Risk:** **{deepfake_pct}%**")
        md.append(f"- **Neural Voice Clone Probability:** **{voice_pct}%**")
        md.append(f"- **Scene & Lighting Consistency:** **{consistency_pct}%**")
        md.append(f"- **Forensic Red Flags Detected:** **{forensics.get('red_flag_count', 0)}**")
        
        audio = forensics.get("technical_audio", {})
        if audio.get("audio_stream_available"):
            md.append(f"- **Acoustic Stream Analysis:** Codec `{audio.get('codec_name')}`, {audio.get('sample_rate')}Hz, {audio.get('silence_burst_count')} anomalous silence bursts")
        if forensics.get("summary"):
            md.append(f"\n*Forensic Findings:* {forensics.get('summary')}")

    # OSINT Section
    if osint:
        md.append("\n---\n## 🌐 Open-Source Intelligence (OSINT) & IFCN Fact-Checks")
        gfc = osint.get("google_factcheck", {})
        fact_checks = gfc.get("fact_checks_found", [])
        if fact_checks:
            md.append(f"### 🎖️ Certified IFCN Fact-Check Reviews ({len(fact_checks)} found)")
            for fc in fact_checks:
                md.append(f"- **[{fc.get('publisher')}]({fc.get('review_url')}):** Rating **{fc.get('rating')}** — *\"{fc.get('title')}\"*")
        else:
            md.append("No active debunks indexed in Google Fact Check Tools database.")
            
        md.append(f"\n- **High-Trust News Sources:** {osint.get('high_trust_sources', 0)} articles")
        md.append(f"- **Corroborating Evidence:** {osint.get('support_count', 0)} sources")
        md.append(f"- **Contradicting Evidence:** {osint.get('contradiction_count', 0)} sources")
        if osint.get("news_summary"):
            md.append(f"\n*OSINT Synthesis:* {osint.get('news_summary')}")

    # Data Mining Section
    if dm_report:
        md.append("\n---\n## ▦ Data Mining & Narrative Pattern Analysis")
        classification = dm_report.get("classification", {})
        md.append(f"- **Linguistic Model Classification:** `{classification.get('category', 'Standard')}` (Confidence: {round(classification.get('confidence', 0)*100)}%)")
        
        patterns = dm_report.get("pattern_mining", {}).get("patterns", [])
        if patterns:
            md.append("\n### Identified Manipulation Patterns")
            for p in patterns:
                md.append(f"- **{p.get('pattern')}** ({p.get('severity').upper()}): {p.get('description')}")

    # Claim-by-Claim Section
    if claims:
        md.append("\n---\n## 🔍 Claim-by-Claim Evidence Matrix")
        for idx, item in enumerate(claims):
            c = item.get("claim", {})
            v = item.get("verdict", {})
            time_str = c.get("time_str") or f"T+{round(c.get('timestamp_in_video', 0))}s"
            
            md.append(f"\n### Claim #{idx + 1} `[{time_str}]` — {v.get('label', 'unverifiable').upper()} ({round(v.get('confidence', 0)*100)}% Confidence)")
            md.append(f"**Extracted Statement:** *\"{c.get('normalized_text') or c.get('raw_text')}\"*")
            md.append(f"\n**AI Reasoning:** {v.get('reasoning') or v.get('summary')}")
            
            evidence_list = v.get("evidence", [])
            if evidence_list:
                md.append("\n**Citations & Sources:**")
                for ev in evidence_list[:3]:
                    stance = "🟢 SUPPORTS" if ev.get("supports_claim") else "🔴 CONTRADICTS"
                    md.append(f"- [{ev.get('source_title')}]({ev.get('source_url')}) ({ev.get('domain')}, Relevance: {round(ev.get('relevance_score', 0)*100)}%) — {stance}")
                    md.append(f"  > *\"{ev.get('snippet')}\"*")

    md.append("\n---\n*TruthLens AI Intelligence Platform — Research-Grade Multimodal Video Fact-Checking Engine*")
    return "\n".join(md)
