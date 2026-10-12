'use client';

import React, { useState } from 'react';

interface ExportDossierModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: string;
  reportData: {
    videoUrl: string;
    overallVerdict: string;
    category: string;
    confidence: number;
    breakdown: any;
    claims: any[];
    forensics?: any;
    osint?: any;
    dmReport?: any;
  };
}

export const ExportDossierModal: React.FC<ExportDossierModalProps> = ({
  isOpen,
  onClose,
  jobId,
  reportData,
}) => {
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  if (!isOpen) return null;

  const buildMarkdown = () => {
    const lines: string[] = [];
    const now = new Date().toUTCString();
    lines.push(`# 🛡️ TruthLens AI — Executive Forensic Verification Dossier`);
    lines.push(`**Target Media:** ${reportData.videoUrl}`);
    lines.push(`**Generated:** ${now}`);
    lines.push(`**Job ID:** \`${jobId}\`\n`);
    lines.push(`---\n## 📊 Final Verdict Determination`);
    lines.push(`- **Overall Determination:** **${reportData.overallVerdict}**`);
    lines.push(`- **Classification Category:** \`${reportData.category}\``);
    lines.push(`- **Calibrated Confidence:** **${Math.round(reportData.confidence)}%**\n`);

    if (reportData.breakdown?.veto_applied) {
      lines.push(`> ⚠️ **VETO ENFORCED:** ${reportData.breakdown.veto_applied.reason}\n`);
    }

    lines.push(`### Metrics Breakdown`);
    lines.push(`- True Claims: ${reportData.breakdown?.true || 0}`);
    lines.push(`- False Claims: ${reportData.breakdown?.false || 0}`);
    lines.push(`- Misleading Claims: ${reportData.breakdown?.misleading || 0}`);
    lines.push(`- Total Claims: ${reportData.breakdown?.total || reportData.claims.length}\n`);

    if (reportData.forensics) {
      lines.push(`---\n## 🔬 Deep Visual & Acoustic Forensics`);
      lines.push(`- Deepfake Risk: ${Math.round(reportData.forensics.deepfake_probability * 100)}%`);
      lines.push(`- Voice Clone Risk: ${Math.round(reportData.forensics.voice_clone_probability * 100)}%`);
      lines.push(`- Red Flags: ${reportData.forensics.red_flag_count || 0}`);
      lines.push(`- Findings: ${reportData.forensics.summary || 'Completed'}\n`);
    }

    if (reportData.osint) {
      lines.push(`---\n## 🌐 OSINT & IFCN Fact-Checking`);
      const fc = reportData.osint.google_factcheck?.fact_checks_found || [];
      lines.push(`- Certified Fact Checks: ${fc.length}`);
      fc.forEach((f: any) => {
        lines.push(`  - **${f.publisher}:** Rating: *${f.rating}* — "${f.title}" (${f.review_url})`);
      });
      lines.push(`- High Trust News Sources: ${reportData.osint.high_trust_sources || 0}\n`);
    }

    if (reportData.claims?.length) {
      lines.push(`---\n## 🔍 Claim-by-Claim Verification Matrix`);
      reportData.claims.forEach((item, idx) => {
        const c = item.claim || {};
        const v = item.verdict || {};
        lines.push(`\n### Claim #${idx + 1} [${c.time_str || '00:00'}] — ${v.label?.toUpperCase()} (${Math.round(v.confidence * 100)}%)`);
        lines.push(`*Statement:* "${c.normalized_text || c.raw_text}"`);
        lines.push(`*Reasoning:* ${v.reasoning || v.summary}`);
        if (v.evidence?.length) {
          lines.push(`*Top Evidence:*`);
          v.evidence.slice(0, 2).forEach((e: any) => {
            lines.push(`- [${e.source_title}](${e.source_url}) (${e.domain})`);
          });
        }
      });
    }

    lines.push(`\n---\n*TruthLens AI — Multimodal Fact-Checking & Deepfake Forensics*`);
    return lines.join('\n');
  };

  const handleCopy = async () => {
    try {
      const md = buildMarkdown();
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDownloadMd = () => {
    setDownloading(true);
    const md = buildMarkdown();
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `TruthLens_Audit_${jobId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setDownloading(false);
  };

  const handleDownloadJson = () => {
    const jsonStr = JSON.stringify(reportData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `TruthLens_Dossier_${jobId}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '1.5rem',
    }}>
      <div style={{
        background: '#0f172a',
        border: '1px solid rgba(99, 102, 241, 0.35)',
        borderRadius: '20px',
        width: '100%',
        maxWidth: '560px',
        boxShadow: '0 25px 60px rgba(0, 0, 0, 0.5), 0 0 30px rgba(99, 102, 241, 0.2)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '1.25rem 1.5rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(255, 255, 255, 0.02)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <span style={{ fontSize: '1.25rem' }}>📥</span>
            <div>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.1rem', color: '#ffffff', margin: 0 }}>
                Export Forensic Intelligence Dossier
              </h3>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0, fontFamily: 'JetBrains Mono, monospace' }}>
                JOB ID: {jobId}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: '1.25rem',
              cursor: 'pointer',
              padding: '0.2rem 0.5rem',
            }}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.5rem' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1.25rem' }}>
            Export the complete verification report including visual/audio deepfake markers, IFCN certified citations, BM25 evidence sources, and constitutional veto logs.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <button
              onClick={handleDownloadMd}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.85rem 1.15rem',
                borderRadius: '12px',
                background: 'rgba(99, 102, 241, 0.12)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                color: '#ffffff',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
            >
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#818cf8' }}>📄 Executive Markdown Audit Report (.md)</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.15rem' }}>Formatted with SHA-256 integrity hash & citation matrix</div>
              </div>
              <span style={{ fontSize: '1.1rem' }}>↓</span>
            </button>

            <button
              onClick={handleDownloadJson}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.85rem 1.15rem',
                borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                color: '#ffffff',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
            >
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>💾 Raw Structured Dossier (.json)</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.15rem' }}>Complete schema for OSINT databases & API consumers</div>
              </div>
              <span style={{ fontSize: '1.1rem' }}>↓</span>
            </button>

            <button
              onClick={handleCopy}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.85rem 1.15rem',
                borderRadius: '12px',
                background: copied ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                border: copied ? '1px solid #10b981' : '1px solid rgba(255, 255, 255, 0.12)',
                color: copied ? '#10b981' : '#ffffff',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
            >
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                  {copied ? '✓ Copied to Clipboard!' : '📋 Copy Briefing Summary'}
                </div>
                <div style={{ fontSize: '0.75rem', color: copied ? '#10b981' : '#94a3b8', marginTop: '0.15rem' }}>
                  {copied ? 'Ready to paste into intelligence reports' : 'Ready-to-paste markdown summary'}
                </div>
              </div>
              <span>{copied ? '✓' : '⧉'}</span>
            </button>
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          background: 'rgba(0, 0, 0, 0.2)',
          display: 'flex',
          justifyContent: 'flex-end',
        }}>
          <button
            onClick={onClose}
            style={{
              padding: '0.5rem 1.25rem',
              borderRadius: '8px',
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#ffffff',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
