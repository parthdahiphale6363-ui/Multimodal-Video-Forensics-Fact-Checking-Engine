'use client';

import { useState, useEffect, useRef } from 'react';
import { getYouTubeId, detectPlatform, ClaimWithVerdict, VerdictLabel, DomainTrust } from '../lib/mockData';
import MistralCatFooter from '../components/MistralCatFooter';
import PixelWorldBackground, { PixelAnimationControls } from '../components/PixelWorldBackground';
import { ExportDossierModal } from '../components/ExportDossierModal';
import { SystemHealthModal } from '../components/SystemHealthModal';

// ─── Types ──────────────────────────────────────────────────────────────────────
type Stage =
  | 'idle' | 'extracting' | 'transcribing' | 'extracting_claims'
  | 'forensics_analysis' | 'osint_collection' | 'data_mining' | 'verifying'
  | 'done' | 'no_claims_found' | 'extraction_failed' | 'failed';

const PIPELINE_STAGES: Stage[] = [
  'extracting', 'transcribing', 'extracting_claims',
  'forensics_analysis', 'verifying', 'osint_collection', 'data_mining', 'done'
];

const STAGE_LABELS: Record<string, string> = {
  extracting: 'Download', transcribing: 'Transcribe',
  extracting_claims: 'Claims', forensics_analysis: 'Forensics',
  osint_collection: 'OSINT', data_mining: 'Data Mining',
  verifying: 'Verify', done: 'Done',
};
const STAGE_ICONS: Record<string, string> = {
  extracting: '↓', transcribing: '◉', extracting_claims: '◈',
  forensics_analysis: '◇', osint_collection: '◎', data_mining: '▦',
  verifying: '⊘', done: '✓',
};

const VERDICT_ICON: Record<string, string> = {
  true: '✓', false: '✗', misleading: '⚠', unverifiable: '⚠'
};
const VERDICT_COLOR: Record<string, string> = {
  true: '#10b981', false: '#f43f5e', misleading: '#f59e0b', unverifiable: '#f59e0b'
};
const TRUST_LABEL: Record<DomainTrust, string> = {
  high: '✓ High Trust', medium: '~ Medium', low: '⚠ Low', blocked: '✗ Blocked'
};

const STAGE_MSG: Partial<Record<Stage, string>> = {
  extracting: 'Downloading video & extracting audio via yt-dlp…',
  transcribing: 'Transcribing with Groq Whisper AI — this may take a minute…',
  extracting_claims: 'Analysing transcript with LLM to extract verifiable claims…',
  forensics_analysis: 'Running deepfake detection & forensic analysis…',
  osint_collection: 'Collecting OSINT: news, social, geolocation & reverse search…',
  data_mining: 'Running data mining: classification, clustering, outlier detection…',
  verifying: 'Fact-checking each claim with live web search & LLM reasoning…',
};

// ─── Verdict Category Colours ────────────────────────────────────────────────────
function getVerdictCatStyle(cat: string): { color: string; bg: string; border: string } {
  const lc = (cat || '').toLowerCase();
  if (lc.includes('genuine') || lc.includes('authentic') || lc.includes('supported'))
    return { color: '#059669', bg: 'rgba(5,150,105,0.07)', border: 'rgba(5,150,105,0.2)' };
  if (lc.includes('deepfake') || lc.includes('synthetic'))
    return { color: '#7c3aed', bg: 'rgba(124,58,237,0.07)', border: 'rgba(124,58,237,0.2)' };
  if (lc.includes('fake') || lc.includes('misinformation') || lc.includes('deceptive') || lc.includes('debunked'))
    return { color: '#dc2626', bg: 'rgba(220,38,38,0.07)', border: 'rgba(220,38,38,0.2)' };
  if (lc.includes('misleading') || lc.includes('sensationalized') || lc.includes('mixed'))
    return { color: '#d97706', bg: 'rgba(217,119,6,0.07)', border: 'rgba(217,119,6,0.2)' };
  if (lc.includes('manipulated') || lc.includes('context'))
    return { color: '#ea580c', bg: 'rgba(234,88,12,0.07)', border: 'rgba(234,88,12,0.2)' };
  if (lc.includes('unsubstantiated') || lc.includes('inconclusive') || lc.includes('low corroboration') || lc.includes('unverified'))
    return { color: '#0284c7', bg: 'rgba(2,132,199,0.07)', border: 'rgba(2,132,199,0.2)' };
  return { color: '#64748b', bg: 'rgba(100,116,139,0.07)', border: 'rgba(100,116,139,0.2)' };
}

// ─── Gauge Card ──────────────────────────────────────────────────────────────────
function GaugeCard({ icon, label, value, color }: { icon: string; label: string; value: number; color: string }) {
  const status = value >= 75 ? 'Good' : value >= 50 ? 'Moderate' : 'At Risk';
  const statusColor = value >= 75 ? '#059669' : value >= 50 ? '#d97706' : '#dc2626';
  return (
    <div className="score-gauge-card" style={{ '--gauge-color': color } as any}>
      <div className="gauge-icon">{icon}</div>
      <div className="gauge-label">{label}</div>
      <div className="gauge-value" style={{ color }}>{value.toFixed(0)}</div>
      <div className="gauge-bar-bg">
        <div className="gauge-bar-fill" style={{ width: `${value}%` }} />
      </div>
      <div className="gauge-status" style={{ color: statusColor }}>{status}</div>
    </div>
  );
}

// ─── Overall Verdict Banner ──────────────────────────────────────────────────────
function OverallVerdictBanner({
  verdict, breakdown, category, confidence
}: {
  verdict: string; breakdown: any;
  category: string; confidence: number;
}) {
  const s = getVerdictCatStyle(category);
  const pct = Math.round(confidence);

  return (
    <div className="overall-verdict-card" style={{ background: s.bg, border: `2px solid ${s.border}` }}>
      <div className="verdict-glow-overlay" style={{ color: s.color }} />
      <div className="verdict-top-row">
        <div className="verdict-left">
          <div className="verdict-eyebrow" style={{ color: s.color }}>Forensic Verdict</div>
          <div className="verdict-title" style={{ color: s.color }}>{verdict}</div>
          <p className="verdict-subtitle">
            Based on {breakdown.total || 0} factual claims verified via live web search, combined with
            forensic analysis, OSINT intelligence, and data mining algorithms.
          </p>
        </div>
        <div className="confidence-dial-wrap">
          <div className="confidence-dial" style={{ '--dial-pct': pct, color: s.color } as any}>
            <div className="confidence-dial-number">{pct}</div>
            <div className="confidence-dial-label">CONF%</div>
          </div>
          <div className="confidence-dial-title">Overall<br />Confidence</div>
        </div>
      </div>

      {breakdown?.veto_applied && (
        <div style={{
          marginTop: '0.85rem',
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          borderRadius: '12px',
          padding: '0.75rem 1rem',
          display: 'flex',
          gap: '0.65rem',
          alignItems: 'center',
        }}>
          <span style={{ fontSize: '1.2rem' }}>🛡️</span>
          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#ef4444' }}>
              Multi-Modal Verdict Veto Enforced
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', margin: '0.15rem 0 0', fontWeight: 500, lineHeight: 1.4 }}>
              {breakdown.veto_applied.reason}
            </p>
          </div>
        </div>
      )}

      {!verdict.includes('No factual') && (
        <div className="verdict-breakdown-row">
          {breakdown.true > 0 && (
            <div className="breakdown-pill" style={{ background: 'rgba(5,150,105,0.07)', border: '1px solid rgba(5,150,105,0.18)' }}>
              <div className="breakdown-number" style={{ color: '#059669' }}>{breakdown.true}</div>
              <div className="breakdown-label" style={{ color: '#059669' }}>True</div>
            </div>
          )}
          {breakdown.false > 0 && (
            <div className="breakdown-pill" style={{ background: 'rgba(220,38,38,0.07)', border: '1px solid rgba(220,38,38,0.18)' }}>
              <div className="breakdown-number" style={{ color: '#dc2626' }}>{breakdown.false}</div>
              <div className="breakdown-label" style={{ color: '#dc2626' }}>False</div>
            </div>
          )}
          {((breakdown.misleading || 0) + (breakdown.unverifiable || 0)) > 0 && (
            <div className="breakdown-pill" style={{ background: 'rgba(217,119,6,0.07)', border: '1px solid rgba(217,119,6,0.18)' }}>
              <div className="breakdown-number" style={{ color: '#d97706' }}>{(breakdown.misleading || 0) + (breakdown.unverifiable || 0)}</div>
              <div className="breakdown-label" style={{ color: '#d97706' }}>Misleading</div>
            </div>
          )}
          <div className="breakdown-pill" style={{ background: 'rgba(79,70,229,0.06)', border: '1px solid rgba(79,70,229,0.15)' }}>
            <div className="breakdown-number" style={{ color: '#4f46e5' }}>{breakdown.total}</div>
            <div className="breakdown-label" style={{ color: '#4f46e5' }}>Total</div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Forensics Panel ─────────────────────────────────────────────────────────────
function ForensicsPanel({ report }: { report: any }) {
  const [open, setOpen] = useState(true);
  if (!report) return null;

  const deepfakePct = Math.round(report.deepfake_probability * 100);
  const voiceClonePct = Math.round(report.voice_clone_probability * 100);
  const sceneConsistencyPct = Math.round(report.scene_consistency_score * 100);

  return (
    <div className="glass forensics-panel">
      <div className="collapse-header" onClick={() => setOpen(!open)}>
        <div className="section-title" style={{ marginBottom: 0, borderBottom: 'none' }}>
          Forensics Analysis
        </div>
        <span className={`collapse-chevron ${open ? 'open' : ''}`}>▼</span>
      </div>
      {open && (
        <>
          <div className="forensics-grid">
            <div className="forensics-stat-card">
              <div className="forensics-stat-value" style={{ color: deepfakePct >= 50 ? '#7c3aed' : '#059669' }}>
                {deepfakePct}%
              </div>
              <div className="forensics-stat-label">Deepfake Probability</div>
            </div>
            <div className="forensics-stat-card">
              <div className="forensics-stat-value" style={{ color: voiceClonePct >= 50 ? '#dc2626' : '#059669' }}>
                {voiceClonePct}%
              </div>
              <div className="forensics-stat-label">Voice Clone Risk</div>
            </div>
            <div className="forensics-stat-card">
              <div className="forensics-stat-value" style={{ color: sceneConsistencyPct >= 70 ? '#059669' : '#d97706' }}>
                {sceneConsistencyPct}%
              </div>
              <div className="forensics-stat-label">Scene Consistency</div>
            </div>
            <div className="forensics-stat-card">
              <div className="forensics-stat-value" style={{ color: report.red_flag_count === 0 ? '#059669' : report.red_flag_count >= 4 ? '#dc2626' : '#d97706' }}>
                {report.red_flag_count}
              </div>
              <div className="forensics-stat-label">Red Flags</div>
            </div>
          </div>

          {report.is_synthetic && (
            <div style={{
              background: 'rgba(220,38,38,0.08)',
              border: '1px solid rgba(220,38,38,0.25)',
              borderRadius: '12px',
              padding: '0.85rem 1rem',
              marginBottom: '1rem',
              display: 'flex',
              gap: '0.65rem',
              alignItems: 'center',
            }}>
              <span style={{ fontSize: '1.2rem' }}>⚠️</span>
              <div>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#dc2626' }}>
                  Synthetic Media Detected
                </span>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', margin: '0.15rem 0 0', fontWeight: 500 }}>
                  {report.forensics_veto?.reason || 'Synthetic voice cloning or deepfake indicators detected above threshold.'}
                </p>
              </div>
            </div>
          )}

          {report.technical_audio?.audio_stream_available && (
            <div style={{ marginBottom: '1rem', padding: '0.85rem 1rem', background: 'rgba(99,102,241,0.04)', borderRadius: '12px', border: '1px solid rgba(99,102,241,0.15)' }}>
              <p style={{ fontSize: '0.72rem', color: '#4f46e5', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.4rem' }}>Technical Audio Stream Analysis (FFprobe / FFmpeg)</p>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                <span>Codec: <strong style={{ color: 'var(--text-primary)' }}>{report.technical_audio.codec_name || 'N/A'}</strong></span>
                <span>Sample Rate: <strong style={{ color: 'var(--text-primary)' }}>{report.technical_audio.sample_rate ? `${report.technical_audio.sample_rate} Hz` : 'N/A'}</strong></span>
                <span>Channels: <strong style={{ color: 'var(--text-primary)' }}>{report.technical_audio.channels || 'N/A'}</strong></span>
                <span>Bitrate: <strong style={{ color: 'var(--text-primary)' }}>{report.technical_audio.bit_rate_kbps ? `${report.technical_audio.bit_rate_kbps} kbps` : 'N/A'}</strong></span>
                <span>Silence Cuts: <strong style={{ color: report.technical_audio.silence_burst_count >= 6 ? '#dc2626' : 'var(--text-primary)' }}>{report.technical_audio.silence_burst_count}</strong></span>
              </div>
            </div>
          )}

          {report.deepfake_analysis?.analysis_summary && (
            <div style={{ marginBottom: '1rem', padding: '0.9rem', background: 'rgba(124,58,237,0.04)', borderRadius: '12px', borderLeft: '3px solid rgba(124,58,237,0.4)' }}>
              <p style={{ fontSize: '0.72rem', color: '#7c3aed', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.3rem' }}>AI Forensics Analysis</p>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{report.deepfake_analysis.analysis_summary}</p>
            </div>
          )}

          {report.red_flags && report.red_flags.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>Red Flags</p>
              <div className="red-flags-list">
                {report.red_flags.slice(0, 6).map((flag: string, i: number) => (
                  <div key={i} className="red-flag-item">
                    <span className="red-flag-icon">⚠</span>
                    <span>{flag}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.geolocation?.locations_found?.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>Geographic References</p>
              <div className="geo-tags">
                {report.geolocation.locations_found.map((loc: any, i: number) => (
                  <span key={i} className="geo-tag">{loc.type === 'country' ? '🌍' : '🏙️'} {loc.name}</span>
                ))}
              </div>
            </div>
          )}

          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontStyle: 'italic', borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
            {report.summary}
          </p>
        </>
      )}
    </div>
  );
}

// ─── OSINT Panel ─────────────────────────────────────────────────────────────────
function OSINTPanel({ report }: { report: any }) {
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<'news' | 'social' | 'geo' | 'timestamp'>('news');
  if (!report) return null;

  const newsResults = report.news_verification?.news_results || [];
  const socialResults = report.social_signals?.social_results || [];
  const geoVers = report.geo_verification?.geo_verifications || [];
  const timestampIssues = report.timestamp_verification?.timestamp_issues || [];

  return (
    <div className="glass osint-panel">
      <div className="collapse-header" onClick={() => setOpen(!open)}>
        <div className="section-title" style={{ marginBottom: 0, borderBottom: 'none' }}>
          OSINT Intelligence
        </div>
        <span className={`collapse-chevron ${open ? 'open' : ''}`}>▼</span>
      </div>
      {open && (
        <>
          <div className="osint-stat-row">
            <div className="osint-stat-box">
              <div className="osint-stat-number" style={{ color: '#4f46e5' }}>{report.news_verification?.total_news_found || 0}</div>
              <div className="osint-stat-label">News Sources</div>
            </div>
            <div className="osint-stat-box">
              <div className="osint-stat-number" style={{ color: '#059669' }}>{report.news_verification?.high_trust_sources || 0}</div>
              <div className="osint-stat-label">High Trust</div>
            </div>
            <div className="osint-stat-box">
              <div className="osint-stat-number" style={{ color: '#dc2626' }}>{report.contradiction_count || 0}</div>
              <div className="osint-stat-label">Contradictions</div>
            </div>
            <div className="osint-stat-box">
              <div className="osint-stat-number" style={{ color: '#059669' }}>{report.support_count || 0}</div>
              <div className="osint-stat-label">Supporting</div>
            </div>
            <div className="osint-stat-box">
              <div className="osint-stat-number" style={{ color: '#d97706' }}>{report.social_signals?.total_social_found || 0}</div>
              <div className="osint-stat-label">Social Posts</div>
            </div>
          </div>

          {report.osint_veto?.veto && (
            <div style={{
              background: 'rgba(220,38,38,0.08)',
              border: '1px solid rgba(220,38,38,0.25)',
              borderRadius: '12px',
              padding: '0.85rem 1rem',
              marginBottom: '1rem',
              display: 'flex',
              gap: '0.65rem',
              alignItems: 'center',
            }}>
              <span style={{ fontSize: '1.2rem' }}>⚠️</span>
              <div>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#dc2626' }}>
                  OSINT Evidence Veto Enforced
                </span>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', margin: '0.15rem 0 0', fontWeight: 500 }}>
                  {report.osint_veto.reason}
                </p>
              </div>
            </div>
          )}

          {report.potential_recycled_content && (
            <div style={{ background: 'rgba(217,119,6,0.06)', border: '1px solid rgba(217,119,6,0.18)', borderRadius: '10px', padding: '0.8rem 1rem', marginBottom: '1rem', display: 'flex', gap: '0.6rem', alignItems: 'flex-start' }}>
              <span>⚠️</span>
              <p style={{ fontSize: '0.83rem', color: '#d97706', lineHeight: 1.5 }}>
                <strong>Old Footage Warning:</strong> Reverse search found signals suggesting this may be recycled or reused video content presented in a new context.
              </p>
            </div>
          )}

          {report.google_factcheck?.fact_checks_found?.length > 0 && (
            <div style={{ marginBottom: '1.2rem', padding: '0.85rem 1rem', background: 'rgba(5,150,105,0.05)', borderRadius: '12px', border: '1px solid rgba(5,150,105,0.2)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.72rem', color: '#059669', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  Google Fact Check Tools API ({report.google_factcheck.fact_checks_found.length} Certified Reviews)
                </span>
                <span style={{ fontSize: '0.72rem', color: '#dc2626', fontWeight: 700 }}>
                  {report.google_factcheck.debunked_count} Debunked
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {report.google_factcheck.fact_checks_found.map((fc: any, i: number) => (
                  <div key={i} style={{ padding: '0.55rem 0.8rem', background: 'var(--bg-secondary)', borderRadius: '8px', borderLeft: `3px solid ${fc.is_debunk ? '#dc2626' : '#059669'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', marginBottom: '0.2rem' }}>
                      <span style={{ fontWeight: 700, color: 'var(--text-muted)' }}>{fc.publisher}</span>
                      <span style={{ fontWeight: 800, color: fc.is_debunk ? '#dc2626' : '#059669' }}>Verdict: {fc.rating}</span>
                    </div>
                    <a href={fc.review_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.82rem', color: 'var(--accent)', fontWeight: 600 }}>
                      {fc.title} ↗
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="tab-bar">
            {(['news', 'social', 'geo', 'timestamp'] as const).map(t => (
              <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
                {{ news: `News (${newsResults.length})`, social: `Social (${socialResults.length})`, geo: `Geolocation`, timestamp: `Timeline` }[t]}
              </button>
            ))}
          </div>

          {tab === 'news' && (
            <div>
              {newsResults.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No news sources found for this content.</p>
              ) : (
                newsResults.slice(0, 5).map((r: any, i: number) => (
                  <div key={i} className="osint-source-card">
                    <div className="osint-source-meta">
                      <span className={`trust-pill trust-${r.domain_trust}`}>{TRUST_LABEL[r.domain_trust as DomainTrust]}</span>
                      <span className="ev-domain">📍 {r.domain}</span>
                      {r.published_date && <span className="ev-date">📅 {r.published_date}</span>}
                    </div>
                    <a href={r.url} target="_blank" rel="noreferrer" className="osint-source-title">{r.title} ↗</a>
                    {r.snippet && <p className="osint-source-snippet">"{r.snippet.slice(0, 160)}"</p>}
                  </div>
                ))
              )}
            </div>
          )}

          {tab === 'social' && (
            <div>
              {socialResults.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No social media discussions found.</p>
              ) : (
                socialResults.slice(0, 5).map((r: any, i: number) => (
                  <div key={i} className="osint-source-card">
                    <div className="osint-source-meta">
                      <span style={{ fontSize: '0.72rem', color: '#4f46e5', fontWeight: 700, background: 'rgba(79,70,229,0.06)', border: '1px solid rgba(79,70,229,0.15)', borderRadius: '99px', padding: '0.12rem 0.5rem' }}>
                        {r.platform || 'Social'}
                      </span>
                      <span className="ev-domain">{r.domain}</span>
                    </div>
                    <a href={r.url} target="_blank" rel="noreferrer" className="osint-source-title">{r.title} ↗</a>
                    {r.snippet && <p className="osint-source-snippet">"{r.snippet.slice(0, 140)}"</p>}
                  </div>
                ))
              )}
              {(report.social_signals?.manipulation_signals?.length > 0) && (
                <div style={{ marginTop: '0.75rem', background: 'rgba(220,38,38,0.05)', border: '1px solid rgba(220,38,38,0.15)', borderRadius: '10px', padding: '0.8rem' }}>
                  <p style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 700, marginBottom: '0.4rem' }}>Social Manipulation Signals</p>
                  {report.social_signals.manipulation_signals.map((s: string, i: number) => (
                    <p key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>• {s}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'geo' && (
            <div>
              <p style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                {report.geo_verification?.geo_summary || 'No geographic verification data.'}
              </p>
              {geoVers.length > 0 && geoVers.slice(0, 4).map((g: any, i: number) => (
                <div key={i} className="osint-source-card" style={{ borderLeft: g.geo_contradicts ? '3px solid #f43f5e' : g.geo_supports ? '3px solid #10b981' : undefined }}>
                  <div className="osint-source-meta">
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: g.geo_contradicts ? '#dc2626' : g.geo_supports ? '#059669' : 'var(--text-muted)' }}>
                      {g.geo_contradicts ? 'Contradicts' : g.geo_supports ? 'Supports' : 'Neutral'}
                    </span>
                    <span className={`trust-pill trust-${g.domain_trust}`}>{TRUST_LABEL[g.domain_trust as DomainTrust]}</span>
                    <span style={{ fontSize: '0.72rem', color: '#4f46e5', fontWeight: 700 }}>{g.location}</span>
                  </div>
                  <a href={g.url} target="_blank" rel="noreferrer" className="osint-source-title">{g.source} ↗</a>
                </div>
              ))}
            </div>
          )}

          {tab === 'timestamp' && (
            <div>
              <p style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                {report.timestamp_verification?.timestamp_summary || 'No timestamp issues detected.'}
              </p>
              {timestampIssues.length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  {timestampIssues.map((issue: string, i: number) => (
                    <div key={i} className="red-flag-item">
                      <span className="red-flag-icon">⏰</span>
                      <span>{issue}</span>
                    </div>
                  ))}
                </div>
              )}
              {report.weather_verification?.weather_claims_found?.length > 0 && (
                <div>
                   <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>Weather Claims</p>
                  <div className="geo-tags">
                    {report.weather_verification.weather_claims_found.map((w: string, i: number) => (
                      <span key={i} className="geo-tag">{w}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontStyle: 'italic', borderTop: '1px solid var(--border)', paddingTop: '0.75rem', marginTop: '0.75rem' }}>
            {report.summary}
          </p>
        </>
      )}
    </div>
  );
}

// ─── Data Mining Panel ───────────────────────────────────────────────────────────
function DataMiningPanel({ report }: { report: any }) {
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<'patterns' | 'clusters' | 'outliers' | 'rules' | 'similarity'>('patterns');
  if (!report) return null;

  const classification = report.classification || {};
  const clusters = report.clustering?.clusters || [];
  const outliers = report.outlier_detection?.outliers || [];
  const rules = report.association_rules?.strong_rules || [];
  const patterns = report.pattern_mining?.patterns || [];
  const similarity = report.similarity_analysis?.template_matches || [];

  return (
    <div className="glass dm-panel">
      <div className="collapse-header" onClick={() => setOpen(!open)}>
        <div className="section-title" style={{ marginBottom: 0, borderBottom: 'none' }}>
          Data Mining Analysis
        </div>
        <span className={`collapse-chevron ${open ? 'open' : ''}`}>▼</span>
      </div>
      {open && (
        <>
          {/* Classification Result */}
          {classification.category && (
            <div style={{
              background: getVerdictCatStyle(classification.category).bg,
              border: `1px solid ${getVerdictCatStyle(classification.category).border}`,
              borderRadius: '14px', padding: '1.1rem 1.35rem', marginBottom: '1.25rem',
              display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap'
            }}>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.12em', color: getVerdictCatStyle(classification.category).color, marginBottom: '0.25rem' }}>
                  DM Narrative Classification
                </p>
                <p style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.3rem', fontWeight: 800, color: getVerdictCatStyle(classification.category).color }}>
                  {classification.category}
                </p>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                  Suspicion score: {(classification.suspicion_score * 100).toFixed(0)}% · Pattern Confidence: {(classification.confidence * 100).toFixed(0)}%
                </p>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: '2rem', fontWeight: 900, color: getVerdictCatStyle(classification.category).color }}>
                  {Math.round(classification.confidence * 100)}%
                </div>
                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Confidence</div>
              </div>
            </div>
          )}

          {report.dm_veto?.veto && (
            <div style={{
              background: 'rgba(217,119,6,0.08)',
              border: '1px solid rgba(217,119,6,0.25)',
              borderRadius: '12px',
              padding: '0.85rem 1rem',
              marginBottom: '1rem',
              display: 'flex',
              gap: '0.65rem',
              alignItems: 'center',
            }}>
              <span style={{ fontSize: '1.2rem' }}>⚡</span>
              <div>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#d97706' }}>
                  Data Mining Pattern Governor Override
                </span>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', margin: '0.15rem 0 0', fontWeight: 500 }}>
                  {report.dm_veto.reason}
                </p>
              </div>
            </div>
          )}

          {report.calibrated_claims_count > 0 && (
            <div style={{ fontSize: '0.78rem', color: '#6366f1', marginBottom: '1rem', padding: '0.5rem 0.85rem', background: 'rgba(99,102,241,0.06)', borderRadius: '10px', border: '1px solid rgba(99,102,241,0.18)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🎯</span>
              <span><strong>Active Calibration:</strong> Re-weighted confidence for {report.calibrated_claims_count} claim{report.calibrated_claims_count > 1 ? 's' : ''} based on outlier detection and deceptive template patterns.</span>
            </div>
          )}

          {/* DM Stats Row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '0.65rem', marginBottom: '1.25rem' }}>
            {[
              ['Clusters', report.clustering?.cluster_count ?? 0, '#4f46e5'],
              ['Outliers', report.outlier_detection?.outlier_count ?? 0, '#f59e0b'],
              ['Patterns', report.pattern_mining?.pattern_count ?? 0, '#7c3aed'],
              ['Assoc Rules', report.association_rules?.total_rules ?? 0, '#059669'],
              ['Template Matches', report.similarity_analysis?.total_matches ?? 0, '#dc2626'],
            ].map(([label, val, color]) => (
              <div key={label as string} className="score-cell">
                <div className="score-label">{label}</div>
                <div className="score-value" style={{ color: color as string }}>{val}</div>
              </div>
            ))}
          </div>

          {/* Tabs */}
          <div className="tab-bar">
            {(['patterns', 'clusters', 'outliers', 'rules', 'similarity'] as const).map(t => (
              <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
                {{ patterns: 'Patterns', clusters: 'Clusters', outliers: 'Outliers', rules: 'Rules', similarity: 'Similarity' }[t]}
              </button>
            ))}
          </div>

          {tab === 'patterns' && (
            <div>
              {patterns.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No suspicious linguistic patterns detected.</p>
              ) : (
                patterns.map((p: any, i: number) => (
                  <div key={i} className={`pattern-card ${p.severity}`}>
                    <div className="pattern-name" style={{ color: p.severity === 'high' ? '#f43f5e' : p.severity === 'medium' ? '#f59e0b' : 'var(--text-primary)' }}>
                      {p.pattern} <span style={{ fontSize: '0.65rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', opacity: 0.7 }}>({p.severity} severity)</span>
                    </div>
                    <p className="pattern-desc">{p.description}</p>
                    {p.indicators?.length > 0 && (
                      <div className="pattern-tags">
                        {p.indicators.slice(0, 5).map((ind: string, j: number) => (
                          <span key={j} className="pattern-tag">"{ind}"</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {tab === 'clusters' && (
            <div>
              {clusters.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No claims to cluster.</p>
              ) : (
                clusters.map((c: any) => (
                  <div key={c.cluster_id} className="cluster-card">
                    <div className="cluster-num">#{c.cluster_id}</div>
                    <div className="cluster-body">
                      <p className="cluster-text">{c.representative_claim || 'No representative claim'}</p>
                      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.35rem', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{c.size} claim{c.size !== 1 ? 's' : ''}</span>
                        <span className={`badge badge-${c.dominant_verdict}`} style={{ fontSize: '0.65rem', padding: '0.1rem 0.5rem' }}>
                          {c.dominant_verdict}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {tab === 'outliers' && (
            <div>
              {outliers.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>✅ No anomalous claims detected.</p>
              ) : (
                outliers.map((o: any, i: number) => (
                  <div key={i} className="outlier-item">
                    <div>
                      <span className={`outlier-severity-badge ${o.anomaly_severity}`}>{o.anomaly_severity}</span>
                    </div>
                    <div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', marginBottom: '0.3rem' }}>"{o.claim_text}"</p>
                      {o.reasons.map((r: string, j: number) => (
                        <p key={j} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>• {r}</p>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {tab === 'rules' && (
            <div>
              {rules.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No strong association rules found.</p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="search-table">
                    <thead>
                      <tr><th>Antecedent</th><th>→ Consequent</th><th>Support</th><th>Confidence</th><th>Lift</th></tr>
                    </thead>
                    <tbody>
                      {rules.map((r: any, i: number) => (
                        <tr key={i}>
                          <td><span className="query-mono">{r.antecedent}</span></td>
                          <td style={{ color: 'var(--text-secondary)', fontSize: '0.78rem' }}>{r.consequent}</td>
                          <td style={{ color: '#4f46e5', fontWeight: 700 }}>{(r.support * 100).toFixed(0)}%</td>
                          <td style={{ color: '#059669', fontWeight: 700 }}>{(r.confidence * 100).toFixed(0)}%</td>
                          <td style={{ color: '#d97706' }}>{r.lift?.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === 'similarity' && (
            <div>
              {similarity.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>✅ No known misinformation templates matched.</p>
              ) : (
                similarity.map((m: any, i: number) => (
                  <div key={i} className="outlier-item">
                    <div>
                      <span className={`outlier-severity-badge ${m.exact_match ? 'high' : 'medium'}`}>
                        {m.match_type}
                      </span>
                    </div>
                    <div>
                      <p style={{ fontSize: '0.82rem', color: '#dc2626', marginBottom: '0.25rem' }}>Template: "{m.template}"</p>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Similarity: {(m.similarity_score * 100).toFixed(0)}%</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontStyle: 'italic', borderTop: '1px solid var(--border)', paddingTop: '0.75rem', marginTop: '0.75rem' }}>
            {report.summary}
          </p>
        </>
      )}
    </div>
  );
}

// ─── Claim Card ───────────────────────────────────────────────────────────────────
function ClaimCard({ item, index, onSeek }: { item: ClaimWithVerdict; index: number; onSeek?: (sec: number) => void }) {
  const { claim, verdict } = item;
  const [tab, setTab] = useState<'verdict' | 'searches' | 'evidence' | 'ai_chain'>('verdict');
  const pct = Math.round((verdict?.confidence ?? 0.5) * 100);
  const s = verdict?.fact_check_summary || {
    searches_run: verdict?.search_runs?.length || 1,
    sources_found: verdict?.evidence?.length || 0,
    sources_accepted: verdict?.evidence?.length || 0,
    sources_blocked: 0,
    consensus_score: verdict?.confidence ?? 0.5,
    cross_platform_hits: 0,
    llm_rounds: verdict?.llm_checks?.length || 1,
    critic_rejections: 0,
  };
  const vColor = (verdict?.label && VERDICT_COLOR[verdict.label]) || 'var(--text-muted)';

  const timeStr = (claim as any)?.time_str || (
    claim?.timestamp_in_video != null
      ? `${String(Math.floor(claim.timestamp_in_video / 60)).padStart(2, '0')}:${String(Math.floor(claim.timestamp_in_video % 60)).padStart(2, '0')}`
      : null
  );
  const timeSec = claim?.timestamp_in_video != null
    ? claim.timestamp_in_video
    : (claim as any)?.time_str
      ? (() => {
          const parts = (claim as any).time_str.split(':').map(Number);
          return parts.length === 2 ? parts[0] * 60 + parts[1] : 0;
        })()
      : null;

  const searchRuns = verdict?.search_runs || [];
  const evidenceList = verdict?.evidence || [];
  const llmChecks = verdict?.llm_checks || [];

  return (
    <div className="glass claim-card" style={{ animationDelay: `${index * 120}ms` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', marginBottom: '0.75rem' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
            <p style={{ fontSize: '0.66rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.09em', margin: 0, fontWeight: 700 }}>
              Claim #{index + 1}{claim?.language ? ` · ${claim.language.toUpperCase()}` : ''}
            </p>
            {timeStr && onSeek && (
              <button
                type="button"
                className="timestamp-jump-btn"
                onClick={() => onSeek(timeSec ?? 0)}
                title={`Jump video & transcript to ${timeStr}`}
              >
                <span>▶</span>
                <span>{timeStr}</span>
              </button>
            )}
          </div>
          <p style={{ fontSize: '1.02rem', fontWeight: 600, lineHeight: 1.5, color: 'var(--text-primary)' }}>"{claim?.normalized_text || (claim as any)?.raw_text || ''}"</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.35rem', flexShrink: 0 }}>
          <span className={`badge badge-${verdict?.label || 'unverifiable'}`}>{VERDICT_ICON[verdict?.label as VerdictLabel] || '?'} {(verdict?.label || 'unverified').toUpperCase()}</span>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: vColor }}>{pct}% confidence</span>
        </div>
      </div>

      {(verdict as any)?.context && (
        <div style={{ background: 'rgba(59,158,255,0.04)', border: '1px solid rgba(59,158,255,0.1)', borderRadius: '10px', padding: '0.6rem 0.85rem', marginBottom: '0.9rem' }}>
          <p style={{ fontSize: '0.68rem', color: 'var(--accent)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.2rem' }}>From Transcript</p>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>"{(verdict as any).context}"</p>
        </div>
      )}

      <div style={{ marginBottom: '1.1rem' }}>
        <div className="confidence-bar-bg" style={{ height: '6px' }}>
          <div className="confidence-bar-fill" style={{ width: `${pct}%` }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
          <span>0%</span><span style={{ color: vColor, fontWeight: 700 }}>{pct}%</span><span>100%</span>
        </div>
      </div>

      <div className="scorecard" style={{ marginBottom: '1.1rem' }}>
        {[
          ['Searches Run', s.searches_run ?? (searchRuns.length || 1), ''],
          ['Sources Found', s.sources_found ?? evidenceList.length, ''],
          ['Accepted', s.sources_accepted ?? evidenceList.length, 'good'],
          ['Blocked', s.sources_blocked ?? 0, (s.sources_blocked ?? 0) > 0 ? 'bad' : ''],
          ['Consensus', `${Math.round(((s.consensus_score ?? verdict?.confidence ?? 0.5) * 100))}%`, ((s.consensus_score ?? 0.5) >= 0.8) ? 'good' : ((s.consensus_score ?? 0.5) >= 0.6) ? 'warn' : 'bad'],
          ['AI Rounds', s.llm_rounds ?? (llmChecks.length || 1), ''],
        ].map(([label, val, cls]) => (
          <div key={label as string} className="score-cell">
            <div className="score-label">{label}</div>
            <div className={`score-value ${cls}`}>{val}</div>
          </div>
        ))}
      </div>

      <div className={`verdict-banner verdict-banner-${verdict?.label || 'unverifiable'}`} style={{ marginBottom: '1.1rem' }}>
        <span className="verdict-icon">{VERDICT_ICON[verdict?.label as VerdictLabel] || '?'}</span>
        <div>
          <p className="verdict-summary-title">Verdict: {(verdict?.label || 'unverified').toUpperCase()}</p>
          <p className="verdict-summary-text">{verdict?.summary || ''}</p>
        </div>
      </div>

      <div className="tab-bar">
        {(['verdict', 'searches', 'evidence', 'ai_chain'] as const).map(t => (
          <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {{
              verdict: 'Reasoning',
              searches: `Searches (${searchRuns.length || s.searches_run || 1})`,
              evidence: `Evidence (${evidenceList.length})`,
              ai_chain: 'AI Chain'
            }[t]}
          </button>
        ))}
      </div>

      {tab === 'verdict' && (
        <div>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.7, borderLeft: '2px solid var(--border-active)', paddingLeft: '0.85rem', marginBottom: '0.85rem' }}>
            {verdict?.reasoning || 'No detailed reasoning available.'}
          </p>

          {/* Atomic Claim Decomposition */}
          {verdict?.atomic_assessments && verdict.atomic_assessments.length > 0 && (
            <div style={{ marginTop: '0.85rem', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border)', borderRadius: '10px', padding: '0.75rem 0.85rem' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent)', marginBottom: '0.55rem' }}>
                Atomic Claim Assessments ({verdict.atomic_assessments.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                {verdict.atomic_assessments.map((atom: any, aIdx: number) => {
                  const aColor = VERDICT_COLOR[atom.verdict as VerdictLabel] || '#f59e0b';
                  return (
                    <div key={atom.id || aIdx} style={{ background: 'rgba(0,0,0,0.18)', borderRadius: '8px', padding: '0.6rem 0.75rem', borderLeft: `3px solid ${aColor}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>{atom.atomic_claim}</span>
                        <span className={`badge badge-${atom.verdict || 'misleading'}`} style={{ fontSize: '0.65rem' }}>
                          {(atom.verdict || 'misleading').toUpperCase()}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>{atom.reasoning}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Unresolved Uncertainties */}
          {verdict?.unresolved_uncertainties && verdict.unresolved_uncertainties.length > 0 && (
            <div style={{ marginTop: '0.75rem', background: 'rgba(245, 158, 11, 0.06)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: '10px', padding: '0.65rem 0.85rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#f59e0b', marginBottom: '0.3rem' }}>
                ⚠️ Missing Context & Unresolved Uncertainties
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                {verdict.unresolved_uncertainties.map((u: string, uIdx: number) => (
                  <li key={uIdx}>{u}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Canonical Audit Hash */}
          {verdict?.canonical_hash && (
            <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              <span>Deterministic Verification Hash:</span>
              <code style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)' }}>
                {verdict.canonical_hash}
              </code>
            </div>
          )}
        </div>
      )}

      {tab === 'searches' && (
        <div style={{ overflowX: 'auto' }}>
          {searchRuns.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', padding: '1rem' }}>No search queries recorded for this claim.</p>
          ) : (
            <table className="search-table">
              <thead><tr><th>#</th><th>Query</th><th>Source</th><th>Results</th><th>Domain</th><th>Trust</th><th>Stance</th></tr></thead>
              <tbody>
                {searchRuns.map((run, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--text-muted)', fontWeight: 700 }}>#{i + 1}</td>
                    <td><span className="query-mono">{run.query}</span></td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>{run.source_type}</td>
                    <td><span className="results-count">{run.results_found}</span></td>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{run.top_domain}</td>
                    <td><span className={`trust-pill trust-${run.trust_level}`}>{TRUST_LABEL[run.trust_level as DomainTrust] || run.trust_level}</span></td>
                    <td><span className={`stance-pill stance-${run.stance}`}>{run.stance}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'evidence' && (
        <div>
          {evidenceList.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', padding: '1rem' }}>No web evidence found for this claim.</p>
          ) : evidenceList.map((ev, i) => {
            const relPct = Math.round((ev.relevance_score ?? 0.8) * 100);
            const relColor = (ev.relevance_score ?? 0.8) >= 0.85 ? '#059669' : (ev.relevance_score ?? 0.8) >= 0.65 ? '#d97706' : '#64748b';
            return (
              <div key={i} className="ev-card">
                <div className="ev-meta">
                  <span className={`trust-pill trust-${ev.domain_trust}`}>{TRUST_LABEL[ev.domain_trust] || ev.domain_trust}</span>
                  <span className="ev-domain">📍 {ev.domain}</span>
                  <span className="ev-date">📅 {ev.publication_date}</span>
                </div>
                <a href={ev.source_url} target="_blank" rel="noreferrer" className="ev-title">{ev.source_title} ↗</a>
                <p className="ev-snippet">"{ev.snippet}"</p>
                {ev.quote && (
                  <div style={{ margin: '0.45rem 0', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '8px', padding: '0.55rem 0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        {ev.quote_verified ? '✓ Verified Verbatim Passage' : 'Extracted Source Passage'}
                      </span>
                      {ev.quote_location && (
                        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Location: {ev.quote_location}</span>
                      )}
                    </div>
                    <blockquote style={{ margin: 0, fontSize: '0.8rem', fontStyle: 'italic', color: 'var(--text-primary)', lineHeight: 1.45 }}>
                      "{ev.quote}"
                    </blockquote>
                  </div>
                )}
                {ev.credibility_limitation && (
                  <div style={{ margin: '0.35rem 0', fontSize: '0.72rem', color: '#f59e0b', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.15)', padding: '3px 8px', borderRadius: '6px' }}>
                    ⚠️ Limitation: {ev.credibility_limitation}
                  </div>
                )}
                <div className="ev-footer">
                  <span className="ev-stance-icon">
                    {(ev as any).stance === 'supports' || ev.supports_claim === true ? '🟢 Supports' :
                     (ev as any).stance === 'contradicts' || ev.supports_claim === false ? '🔴 Contradicts' :
                     (ev as any).stance === 'mixed' ? '🟡 Mixed' :
                     (ev as any).stance === 'irrelevant' ? '⚪ Irrelevant' : '⚪ Insufficient'}
                  </span>
                  {(ev as any).is_independent === false && (
                    <span style={{ fontSize: '0.68rem', background: 'rgba(148,163,184,0.15)', color: '#94a3b8', padding: '2px 7px', borderRadius: '4px', fontWeight: 600 }}>
                      Syndicated Wire
                    </span>
                  )}
                  <div className="relevance-bar-bg"><div className="relevance-bar-fill" style={{ width: `${relPct}%`, background: relColor }} /></div>
                  <span style={{ fontSize: '0.72rem', color: relColor, fontWeight: 700, flexShrink: 0 }}>Relevance {relPct}%</span>
                </div>
                {(ev as any).explanation && (
                  <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '0.35rem', lineHeight: 1.4 }}>
                    💡 {(ev as any).explanation}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {tab === 'ai_chain' && (
        <div className="agent-chain">
          {llmChecks.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', padding: '1rem' }}>No AI chain steps recorded.</p>
          ) : llmChecks.map((check, i) => (
            <div key={i} className="agent-step">
              <div className="agent-left">
                <div className={`agent-icon ${check.passed ? 'pass' : 'fail'}`}>{check.passed ? '✓' : '↩'}</div>
              </div>
              <div className="agent-body">
                <p className="agent-name">{check.agent}</p>
                <p className="agent-role">{check.role}</p>
                <p className="agent-finding">{check.finding}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────────
export default function Home() {
  const [url, setUrl] = useState('');
  const [stage, setStage] = useState<Stage>('idle');
  const [progress, setProgress] = useState(0);
  const [ytId, setYtId] = useState<string | null>(null);
  const [platform, setPlatform] = useState<string>('youtube');
  const [transcriptLines, setTranscriptLines] = useState<{ time: string; text: string }[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [realClaims, setRealClaims] = useState<ClaimWithVerdict[]>([]);
  const [overallVerdict, setOverallVerdict] = useState<string | null>(null);
  const [verdictBreakdown, setVerdictBreakdown] = useState<Record<string, number> | null>(null);
  const [finalVerdictCategory, setFinalVerdictCategory] = useState<string>('Unverified');
  const [overallConfidence, setOverallConfidence] = useState<number>(0);
  const [videoScore, setVideoScore] = useState<number>(0);
  const [audioScore, setAudioScore] = useState<number>(0);
  const [metadataScore, setMetadataScore] = useState<number>(0);
  const [osintScore, setOsintScore] = useState<number>(0);
  const [dmScore, setDmScore] = useState<number>(0);
  const [forensicsReport, setForensicsReport] = useState<any>(null);
  const [osintReport, setOsintReport] = useState<any>(null);
  const [dmReport, setDmReport] = useState<any>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // 10/10 Interactive Modals & Filtering States
  const [showExportModal, setShowExportModal] = useState(false);
  const [showHealthModal, setShowHealthModal] = useState(false);
  const [claimFilter, setClaimFilter] = useState<'all' | 'true' | 'false' | 'misleading'>('all');
  const [claimSearch, setClaimSearch] = useState('');
  const [seekSec, setSeekSec] = useState<number | null>(null);
  const [activeDemoCase, setActiveDemoCase] = useState<string | null>(null);
  const [idleTab, setIdleTab] = useState<'cases' | 'pipeline'>('cases');

  const stageIndex = PIPELINE_STAGES.indexOf(stage as any);
  const isProcessing = !['idle', 'done', 'no_claims_found', 'extraction_failed', 'failed'].includes(stage);

  // Lock scrolling strictly on idle landing page
  useEffect(() => {
    if (stage === 'idle') {
      document.documentElement.classList.add('idle-no-scroll');
      document.body.classList.add('idle-no-scroll');
    } else {
      document.documentElement.classList.remove('idle-no-scroll');
      document.body.classList.remove('idle-no-scroll');
    }
    return () => {
      document.documentElement.classList.remove('idle-no-scroll');
      document.body.classList.remove('idle-no-scroll');
    };
  }, [stage]);

  // ── Poll Job Status + incremental results ──
  useEffect(() => {
    if (!jobId || !isProcessing) return;
    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) {
          if (res.status === 404) {
            setErrorMessage('Job session not found or server was restarted. Please re-submit your analysis.');
            setStage('failed');
            return true;
          }
          return false;
        }
        const job = await res.json();
        setProgress(job.progress_percent ?? 0);
        const s = job.status as Stage;

        if (s === 'failed') { setErrorMessage(job.error_message || 'Unexpected error.'); setStage('failed'); return true; }
        if (s === 'extraction_failed') { setErrorMessage(job.error_message || 'Claim extraction failed.'); setStage('extraction_failed'); return true; }
        if (s === 'no_claims_found') {
          setOverallVerdict(job.overall_verdict || 'No verifiable factual claims found');
          setVerdictBreakdown(job.verdict_breakdown || {});
          setStage('no_claims_found'); return true;
        }

        const validStages: Stage[] = ['extracting', 'transcribing', 'extracting_claims', 'forensics_analysis', 'verifying', 'osint_collection', 'data_mining'];
        if (validStages.includes(s)) setStage(s);

        // Incremental: fetch transcript as soon as available
        if (['extracting_claims', 'forensics_analysis', 'verifying', 'osint_collection', 'data_mining'].includes(s)) {
          try {
            const tRes = await fetch(`/api/jobs/${jobId}/transcript`);
            if (tRes.ok) {
              const tData = await tRes.json();
              if (Array.isArray(tData) && tData.length > 0) {
                setTranscriptLines(tData.map((seg: any) => ({
                  time: `${String(Math.floor(seg.start / 60)).padStart(2, '0')}:${String(Math.floor(seg.start % 60)).padStart(2, '0')}`,
                  text: seg.text,
                })));
              }
            }
          } catch {}
        }

        // Incremental: fetch claims as they are verified
        if (['verifying', 'osint_collection', 'data_mining'].includes(s)) {
          try {
            const cRes = await fetch(`/api/jobs/${jobId}/claims`);
            if (cRes.ok) {
              const claims = await cRes.json();
              if (Array.isArray(claims) && claims.length > 0) setRealClaims(claims);
            }
          } catch {}
        }

        // Incremental: fetch forensics when ready
        if (['forensics_analysis', 'verifying', 'osint_collection', 'data_mining'].includes(s)) {
          try {
            const fRes = await fetch(`/api/jobs/${jobId}/forensics`);
            if (fRes.ok) setForensicsReport(await fRes.json());
          } catch {}
        }

        if (s === 'done') {
          const tRes = await fetch(`/api/jobs/${jobId}/transcript`);
          const tData = await tRes.json();
          setTranscriptLines((tData as any[]).map((seg: any) => ({
            time: `${String(Math.floor(seg.start / 60)).padStart(2, '0')}:${String(Math.floor(seg.start % 60)).padStart(2, '0')}`,
            text: seg.text,
          })));
          const cRes = await fetch(`/api/jobs/${jobId}/claims`);
          setRealClaims(await cRes.json());
          try { const fRes = await fetch(`/api/jobs/${jobId}/forensics`); if (fRes.ok) setForensicsReport(await fRes.json()); } catch {}
          try { const oRes = await fetch(`/api/jobs/${jobId}/osint`); if (oRes.ok) setOsintReport(await oRes.json()); } catch {}
          try { const dRes = await fetch(`/api/jobs/${jobId}/dm_report`); if (dRes.ok) setDmReport(await dRes.json()); } catch {}
          setOverallVerdict(job.overall_verdict || null);
          setVerdictBreakdown(job.verdict_breakdown || null);
          setFinalVerdictCategory(job.final_verdict_category || 'Unverified');
          setOverallConfidence(job.overall_confidence || 0);
          setVideoScore(job.video_score || 0);
          setAudioScore(job.audio_score || 0);
          setMetadataScore(job.metadata_score || 0);
          setOsintScore(job.osint_score || 0);
          setDmScore(job.dm_score || 0);
          setStage('done');
          return true;
        }
      } catch (e) { console.error(e); }
      return false;
    };

    poll();
    const interval = setInterval(async () => {
      const finished = await poll();
      if (finished) clearInterval(interval);
    }, 8000);
    return () => clearInterval(interval);
  }, [jobId, isProcessing]);

  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [transcriptLines]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanUrl = url.trim();
    if (!cleanUrl) return;

    // Validate that input is specifically a YouTube Shorts URL
    const isShorts = cleanUrl.includes('/shorts/') || cleanUrl.includes('shorts/');
    const isLocalOrTest = cleanUrl.includes('localhost') || cleanUrl.includes('127.0.0.1') || cleanUrl.includes('example.com') || cleanUrl.startsWith('/');
    
    if (!isShorts && !isLocalOrTest) {
      setErrorMessage('Please enter only a YouTube Shorts URL (e.g., https://www.youtube.com/shorts/VIDEO_ID). TruthLens AI is designed specifically for short-form viral video verification.');
      setStage('failed');
      return;
    }

    setYtId(getYouTubeId(cleanUrl)); setPlatform(detectPlatform(cleanUrl));
    setTranscriptLines([]); setRealClaims([]); setJobId(null);
    setOverallVerdict(null); setVerdictBreakdown(null); setErrorMessage(null);
    setForensicsReport(null); setOsintReport(null); setDmReport(null);
    setFinalVerdictCategory('Unverified'); setOverallConfidence(0);
    setVideoScore(0); setAudioScore(0); setMetadataScore(0); setOsintScore(0); setDmScore(0);
    setActiveDemoCase(null); setSeekSec(null); setClaimFilter('all'); setClaimSearch('');
    setStage('extracting'); setProgress(5);
    try {
      const res = await fetch('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ video_url: cleanUrl }) });
      if (res.ok) { const job = await res.json(); setJobId(job.id); }
      else { setErrorMessage('Failed to submit job. Is the backend running?'); setStage('failed'); }
    } catch { setErrorMessage('Failed to connect to backend. Please check that the server is running.'); setStage('failed'); }
  };

  const handleSeek = (seconds: number) => {
    setSeekSec(seconds);
  };

  const loadDemoCase = async (caseKey: string) => {
    try {
      const res = await fetch('/api/jobs/demo-cases');
      if (!res.ok) return;
      const data = await res.json();
      const demo = data[caseKey];
      if (!demo) return;

      setActiveDemoCase(caseKey);
      setUrl(demo.video_url);
      setYtId(getYouTubeId(demo.video_url));
      setPlatform(demo.platform || 'youtube');
      setJobId(demo.id);
      setTranscriptLines(demo.transcript.map((seg: any) => ({
        time: `${String(Math.floor(seg.start / 60)).padStart(2, '0')}:${String(Math.floor(seg.start % 60)).padStart(2, '0')}`,
        text: seg.text,
      })));
      setRealClaims(demo.claims);
      setForensicsReport(demo.forensics);
      setOsintReport(demo.osint);
      setDmReport(demo.dm_report);
      setOverallVerdict(demo.overall_verdict);
      setVerdictBreakdown(demo.verdict_breakdown);
      setFinalVerdictCategory(demo.final_verdict_category);
      setOverallConfidence(demo.overall_confidence);
      setVideoScore(demo.video_score);
      setAudioScore(demo.audio_score);
      setMetadataScore(demo.metadata_score);
      setOsintScore(demo.osint_score);
      setDmScore(demo.dm_score);
      setSeekSec(null);
      setClaimFilter('all');
      setClaimSearch('');
      setStage('done');
    } catch (err) {
      console.error('Failed to load demo case:', err);
    }
  };

  const reset = () => {
    setStage('idle'); setUrl(''); setProgress(0); setYtId(null);
    setTranscriptLines([]); setRealClaims([]); setJobId(null);
    setOverallVerdict(null); setVerdictBreakdown(null); setErrorMessage(null);
    setForensicsReport(null); setOsintReport(null); setDmReport(null);
    setFinalVerdictCategory('Unverified'); setOverallConfidence(0);
    setVideoScore(0); setAudioScore(0); setMetadataScore(0); setOsintScore(0); setDmScore(0);
    setActiveDemoCase(null); setSeekSec(null); setClaimFilter('all'); setClaimSearch('');
  };

  const MODULE_CARDS = [
    { icon: '↓', name: 'Data Collection', desc: 'Audio extraction & video metadata' },
    { icon: '◇', name: 'Forensics', desc: 'Deepfake, voice-clone & manipulation detection' },
    { icon: '▦', name: 'Data Mining', desc: 'Classification, clustering & outlier detection' },
    { icon: '◈', name: 'LLM Analysis', desc: 'Groq LLM reasoning & claim extraction' },
    { icon: '⊘', name: 'Fact Checking', desc: 'Live web search verification per claim' },
    { icon: '◻', name: 'Explainable AI', desc: 'Confidence metrics, red flags & evidence chain' },
  ];

  return (
    <>
      <PixelWorldBackground />
      <div className={`page-wrap${stage === 'idle' ? ' idle-page-wrap' : ''}`}>
        {/* ── Top Brand Bar ── */}
        <div className="top-brand-bar">
          <div className="top-brand-left">
            <div className="brand-badge-pill">
              <span className="brand-dot" />
              <span className="brand-name">TruthLens AI</span>
              <span className="brand-sep">•</span>
              <span className="brand-tag">FORENSICS ENGINE v2.4</span>
            </div>
            <button
              type="button"
              className="system-health-pill"
              onClick={() => setShowHealthModal(true)}
              title="Inspect live system diagnostics & API circuit breakers"
            >
              <span className="live-status-dot" />
              <span>System: Operational</span>
              <span className="system-health-ping">[Diagnostics ↗]</span>
            </button>
          </div>
          <div className="top-brand-right">
            <PixelAnimationControls />
          </div>
        </div>

      {/* ── Hero & Main Content ── */}
      {stage === 'idle' ? (
        <div className="idle-hero-center">
          <header className="site-header">
            <div className="site-header-badge">
              <span className="badge-sparkle">✦</span>
              RESEARCH-GRADE FORENSICS • EXPLAINABLE AI • OSINT
            </div>
            <h1 className="hero-title">
              Multimodal Video Forensics
              <span className="gradient-highlight">
                <span className="title-amp">&amp;</span> Fact-Checking Engine
              </span>
            </h1>
            <p className="hero-subtitle">
              Detect deepfakes, inspect voice &amp; video forensics, mine <span style={{ whiteSpace: 'nowrap' }}>cross-platform</span> OSINT signals,
              and verify claims with explainable AI verdicts.
            </p>
            <div className="pipeline-stepper-ribbon">
              {[
                { icon: '↓', label: 'Ingest' },
                { icon: '◉', label: 'Transcribe' },
                { icon: '◈', label: 'Claims' },
                { icon: '◇', label: 'Forensics' },
                { icon: '▦', label: 'Data Mining' },
                { icon: '⊘', label: 'Verify' },
                { icon: '✓', label: 'Verdict' },
              ].map((step, idx, arr) => (
                <div key={step.label} className="stepper-item">
                  <div className="stepper-pill">
                    <span className="stepper-icon">{step.icon}</span>
                    <span className="stepper-label">{step.label}</span>
                  </div>
                  {idx < arr.length - 1 && <span className="stepper-arrow">›</span>}
                </div>
              ))}
            </div>
          </header>

          <div className="url-section">
          <form onSubmit={handleSubmit} className="url-form-container">
            <div className="url-command-bar">
              <div className="url-platform-icon" title="YouTube Shorts Input">
                <span className="yt-badge">▶</span>
              </div>
              <input
                id="video-url-input"
                type="url"
                className="url-input"
                placeholder="Paste YouTube Shorts URL only (e.g., https://www.youtube.com/shorts/…)…"
                value={url}
                onChange={e => setUrl(e.target.value)}
                required
              />
              {url && (
                <button
                  type="button"
                  className="url-clear-btn"
                  onClick={() => setUrl('')}
                  title="Clear input"
                >
                  ✕
                </button>
              )}
              <button id="analyze-btn" type="submit" className="btn-analyze">
                <span className="btn-sparkle">⚡</span>
                <span>Analyze Shorts</span>
              </button>
            </div>
          </form>

          {/* Unified Sleek Showcase Console */}
          <div className="glass idle-showcase-box">
            <div className="showcase-nav-bar">
              <div className="showcase-tabs">
                <button
                  type="button"
                  className={`showcase-tab ${idleTab === 'cases' ? 'active' : ''}`}
                  onClick={() => setIdleTab('cases')}
                >
                  <span className="tab-sparkle">✨</span>
                  <span>Instant Case Studies</span>
                  <span className="tab-pill-count">3</span>
                </button>
                <button
                  type="button"
                  className={`showcase-tab ${idleTab === 'pipeline' ? 'active' : ''}`}
                  onClick={() => setIdleTab('pipeline')}
                >
                  <span className="tab-sparkle">🔬</span>
                  <span>Verification Pipeline</span>
                  <span className="tab-pill-count">6 Stages</span>
                </button>
              </div>
              <div className="showcase-badge-meta">
                {idleTab === 'cases' ? (
                  <span className="showcase-meta-tag">⚡ Zero-Latency Instant Inspection</span>
                ) : (
                  <span className="showcase-meta-tag">🛡️ Automated Multimodal Intelligence</span>
                )}
              </div>
            </div>

            {idleTab === 'cases' ? (
              <div className="demo-cards-row">
                <div className="demo-card" onClick={() => loadDemoCase('deepfake_scam')} title="Click to inspect this real deepfake case">
                  <div className="demo-card-top">
                    <span className="demo-card-icon">⚡</span>
                    <span className="demo-card-badge" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>Deepfake 94%</span>
                  </div>
                  <div className="demo-card-title">Elon Musk AI Scam &amp; Crypto Bait</div>
                  <div className="demo-card-desc">Synthetic voice cloning, ELA warping, and advance-fee scam veto.</div>
                  <div className="demo-card-action">Inspect Case ↗</div>
                </div>

                <div className="demo-card" onClick={() => loadDemoCase('science_myths')} title="Click to inspect this peer-reviewed science fact-check">
                  <div className="demo-card-top">
                    <span className="demo-card-icon">🧬</span>
                    <span className="demo-card-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>Verified 89%</span>
                  </div>
                  <div className="demo-card-title">Venom Genes &amp; Human Empathy</div>
                  <div className="demo-card-desc">PNAS genomics &amp; Anthrozoös psychology peer-reviewed validation.</div>
                  <div className="demo-card-action">Inspect Case ↗</div>
                </div>

                <div className="demo-card" onClick={() => loadDemoCase('geopolitical_disinfo')} title="Click to inspect this video CGI manipulation case">
                  <div className="demo-card-top">
                    <span className="demo-card-icon">🛡️</span>
                    <span className="demo-card-badge" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>Manipulated 96%</span>
                  </div>
                  <div className="demo-card-title">Recycled Combat Video &amp; Bot CGI</div>
                  <div className="demo-card-desc">ARMA 3 video game CGI recycled as live combat with IFCN debunks.</div>
                  <div className="demo-card-action">Inspect Case ↗</div>
                </div>
              </div>
            ) : (
              <div className="showcase-pipeline-view">
                <div className="module-grid">
                  {MODULE_CARDS.map(m => (
                    <div key={m.name} className="module-card">
                      <div className="module-card-top">
                        <div className="module-icon">{m.icon}</div>
                        <div className="module-name">{m.name}</div>
                      </div>
                      <div className="module-desc">{m.desc}</div>
                    </div>
                  ))}
                </div>
                {/* Capability tags */}
                <div className="floating-stats-row">
                  {[
                    { label: 'Groq LLM', sublabel: 'Llama 3.3 70B' },
                    { label: 'Live Search', sublabel: 'DuckDuckGo Engine' },
                    { label: 'Data Mining', sublabel: 'Pattern & Outliers' },
                    { label: 'Forensics', sublabel: 'Deepfake & Voice' },
                  ].map(s => (
                    <div key={s.label} className="floating-stat">
                      <span className="stat-label">{s.label}</span>
                      <span className="stat-sublabel">{s.sublabel}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      ) : (
        <header className="site-header">
          <div className="site-header-badge">
            <span className="badge-sparkle">✦</span>
            RESEARCH-GRADE FORENSICS • EXPLAINABLE AI • OSINT
          </div>
          <h1 className="hero-title">
            Multimodal Video Forensics
            <span className="gradient-highlight">
              <span className="title-amp">&amp;</span> Fact-Checking Engine
            </span>
          </h1>
          <p className="hero-subtitle">
            Detect deepfakes, inspect voice &amp; video forensics, mine <span style={{ whiteSpace: 'nowrap' }}>cross-platform</span> OSINT signals,
            and verify claims with explainable AI verdicts.
          </p>
        </header>
      )}

      {/* ── Error States ── */}
      {(stage === 'failed' || stage === 'extraction_failed') && (
        <div className="error-box">
          <p style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚠️</p>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.4rem', color: '#dc2626', marginBottom: '0.5rem' }}>
            {stage === 'extraction_failed' ? 'Claim Extraction Failed' : 'Processing Failed'}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>{errorMessage}</p>
          <button className="btn-reset" onClick={reset} style={{ padding: '0.75rem 2rem' }}>↩ Try Again</button>
        </div>
      )}

      {/* ── Processing View ── */}
      {isProcessing && (
        <>
          <div className="glass pipeline-wrap" style={{ marginBottom: '1.5rem', position: 'relative', overflow: 'hidden' }}>
            <div className="scan-ray" />
            <div className="pipeline-stages">
              {PIPELINE_STAGES.filter(s => s !== 'done').map((s, i) => {
                const si = PIPELINE_STAGES.indexOf(s);
                const isDone = stageIndex > si;
                const isActive = stageIndex === si;
                return (
                  <div key={s} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                    <div className="stage-dot-wrap" style={{ flex: 'none', minWidth: 52 }}>
                      <div className={`stage-dot${isActive ? ' active' : isDone ? ' done' : ''}`}>
                        {isDone ? '✓' : STAGE_ICONS[s]}
                      </div>
                      <span className={`stage-label${isActive ? ' active' : isDone ? ' done' : ''}`}>{STAGE_LABELS[s]}</span>
                    </div>
                    {i < PIPELINE_STAGES.filter(s => s !== 'done').length - 1 && (
                      <div className={`stage-connector${isDone ? ' active' : ''}`} style={{ flex: 1 }} />
                    )}
                  </div>
                );
              })}
            </div>
            <div className="progress-bar-wrap">
              <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <div className="processing-status">
              <div className="status-dot" />
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>{STAGE_MSG[stage] || 'Processing…'}</p>
            </div>
          </div>

          <div className="two-col">
            <div className="glass" style={{ overflow: 'hidden', borderRadius: '18px' }}>
              <div className="video-preview-wrap">
                {ytId ? (
                  <iframe src={`https://www.youtube.com/embed/${ytId}?autoplay=1&mute=1&controls=1&rel=0`} allowFullScreen allow="autoplay" title="Video Preview" />
                ) : (
                  <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>📹 Video preview not available</div>
                )}
              </div>
              <div className="video-meta">
                <span className={`platform-badge platform-${platform}`}>{platform === 'youtube' ? '▶' : '📸'} {platform}</span>
              </div>
            </div>

            <div className="glass transcript-panel" style={{ borderRadius: '18px', maxHeight: '340px', overflowY: 'auto' }}>
              <p className="panel-label">
                {stage === 'verifying' && realClaims.length > 0
                  ? `Verified ${realClaims.length} claim${realClaims.length !== 1 ? 's' : ''} so far…`
                  : stage === 'transcribing' ? <><span className="live-dot" />Transcribing audio…</> :
                  stage === 'forensics_analysis' ? 'Running forensic analysis…' :
                  stage === 'osint_collection' ? 'Collecting OSINT data…' :
                  stage === 'data_mining' ? 'Running data mining…' :
                  stage === 'extracting_claims' ? 'Extracting key claims…' :
                  stage === 'verifying' ? 'Verifying claims via web…' : 'Transcript'}
              </p>
              {realClaims.length > 0 && ['verifying', 'osint_collection', 'data_mining'].includes(stage) ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                  {realClaims.map((item, i) => (
                    <div key={i} style={{ background: 'rgba(59,158,255,0.04)', border: '1px solid rgba(59,158,255,0.1)', borderRadius: '10px', padding: '0.65rem 0.85rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.3rem' }}>
                        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 700 }}>Claim #{i + 1}</span>
                        <span className={`badge badge-${item.verdict?.label || 'unverifiable'}`}>{(item.verdict?.label || 'unverified').toUpperCase()}</span>
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', lineHeight: 1.45 }}>"{item.claim.normalized_text}"</p>
                      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                        {item.verdict.evidence?.length || 0} sources · {Math.round(item.verdict.confidence * 100)}% confidence
                      </p>
                    </div>
                  ))}
                </div>
              ) : transcriptLines.length > 0 ? (
                <div className="transcript-text">
                  {transcriptLines.map((line, i) => (
                    <div key={i} className="transcript-segment">
                      <span className="segment-time">[{line.time}]</span>{line.text}
                    </div>
                  ))}
                  <div ref={transcriptEndRef} />
                </div>
              ) : (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '0.75rem', minHeight: 200 }}>
                  <div style={{ width: 36, height: 36, border: '3px solid #e2e8f0', borderTop: '3px solid #4f46e5', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', textAlign: 'center' }}>
                    {stage === 'extracting' ? 'Downloading audio…' :
                      stage === 'verifying' ? 'Searching web & running Groq analysis per claim — this may take 1–2 min…' :
                      stage === 'forensics_analysis' ? 'Analyzing forensic signals…' :
                      stage === 'osint_collection' ? 'Searching open sources…' :
                      stage === 'data_mining' ? 'Mining patterns in data…' :
                      'Processing — results appear when ready'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── No Claims ── */}
      {stage === 'no_claims_found' && (
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '20px', padding: '3rem', textAlign: 'center' }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(100,116,139,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem', fontSize: '1.5rem' }}>?</div>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.5rem', color: 'var(--text-heading)', marginBottom: '0.5rem' }}>No Verifiable Claims Found</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', maxWidth: 500, margin: '0 auto 1.5rem', lineHeight: 1.7 }}>
            The AI analysed the full transcript but found no independently verifiable factual claims. The video may be entertainment, opinion, or informal conversation.
          </p>
          <button className="btn-reset" onClick={reset} style={{ padding: '0.75rem 2rem' }}>Analyze Another Video</button>
        </div>
      )}

      {/* ── Results ── */}
      {stage === 'done' && (
        <div style={{ animation: 'fadeUp 0.5s ease' }}>
          {/* Meta Bar */}
          <div className="glass results-meta-bar" style={{ borderRadius: '16px', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '1.25rem', margin: 0 }}>
                  Analysis Complete — {realClaims.length} claim{realClaims.length !== 1 ? 's' : ''} verified
                </h2>
                {activeDemoCase && (
                  <span style={{ fontSize: '0.65rem', fontWeight: 800, padding: '0.15rem 0.5rem', borderRadius: '6px', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.4)', textTransform: 'uppercase' }}>
                    Demo Case
                  </span>
                )}
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0.25rem 0 0.5rem' }}>
                <a href={url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>
                  {url.slice(0, 72)}{url.length > 72 ? '…' : ''}
                </a>
              </p>
              <div className="api-status-row">
                <span className="api-status-chip live">Groq AI</span>
                <span className="api-status-chip live">News API</span>
                <span className="api-status-chip live">OSINT Engine</span>
                <span className="api-status-chip live">Forensics</span>
                <span className="api-status-chip live">Data Mining</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.65rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn-export"
                onClick={() => setShowExportModal(true)}
                title="Export comprehensive executive audit dossier in Markdown or JSON"
              >
                <span>📥</span>
                <span>Export Dossier</span>
              </button>
              <button className="btn-reset" onClick={reset}>↩ Analyze Another</button>
            </div>
          </div>

          {/* Overall Verdict */}
          {overallVerdict && (
            <OverallVerdictBanner
              verdict={overallVerdict}
              breakdown={verdictBreakdown || {}}
              category={finalVerdictCategory}
              confidence={overallConfidence}
            />
          )}

          {/* Forensics Panel */}
          {forensicsReport && <ForensicsPanel report={forensicsReport} />}

          {/* OSINT Panel */}
          {osintReport && <OSINTPanel report={osintReport} />}

          {/* Data Mining Panel */}
          {dmReport && <DataMiningPanel report={dmReport} />}

          {/* Video + Transcript */}
          <p className="section-title">Video &amp; Transcript Synchronization</p>
          <div className="two-col" style={{ marginBottom: '2rem' }}>
            <div className="glass" style={{ overflow: 'hidden', borderRadius: '18px' }}>
              <div className="video-preview-wrap">
                {ytId ? (
                  <iframe
                    src={`https://www.youtube.com/embed/${ytId}?${seekSec != null ? `start=${Math.floor(seekSec)}&autoplay=1&` : ''}controls=1&rel=0`}
                    allowFullScreen
                    allow="autoplay"
                    title="Video"
                  />
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>📹 Not available</div>
                )}
              </div>
              <div className="video-meta">
                <span className={`platform-badge platform-${platform}`}>{platform}</span>
                {seekSec != null && (
                  <span style={{ fontSize: '0.72rem', color: '#818cf8', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
                    ▶ Seeking {String(Math.floor(seekSec / 60)).padStart(2, '0')}:{String(Math.floor(seekSec % 60)).padStart(2, '0')}
                  </span>
                )}
              </div>
            </div>
            <div className="glass transcript-panel" style={{ borderRadius: '18px', maxHeight: '320px', overflowY: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
                <p className="panel-label" style={{ margin: 0 }}>Full Transcript (Translated to English)</p>
                <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Click timestamp to seek video</span>
              </div>
              <div className="transcript-text">
                {transcriptLines.map((line, i) => {
                  const segSec = (() => {
                    const p = line.time.split(':').map(Number);
                    return p.length === 2 ? p[0] * 60 + p[1] : 0;
                  })();
                  const isHighlighted = seekSec != null && Math.abs(segSec - seekSec) <= 6;
                  return (
                    <div key={i} className={`transcript-segment${isHighlighted ? ' active-seek' : ''}`}>
                      <span
                        className="segment-time"
                        onClick={() => handleSeek(segSec)}
                        style={{ cursor: 'pointer', transition: 'color 0.15s ease' }}
                        title="Click to seek player here"
                      >
                        [{line.time}]
                      </span>
                      {line.text}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Claim Cards */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <div>
              <p className="section-title" style={{ marginBottom: '0.2rem' }}>Claim-by-Claim Fact Check</p>
              <p className="claims-header" style={{ marginBottom: 0 }}>
                {realClaims.length} factual claims extracted by LLM · verified via live web search · Groq reasoning
              </p>
            </div>
          </div>

          {/* Filter & Search Bar */}
          {realClaims.length > 0 && (
            <div className="claim-controls-bar">
              <div className="claim-search-wrap">
                <input
                  type="text"
                  className="claim-search-input"
                  placeholder="Filter claims by keywords, sources, or entities…"
                  value={claimSearch}
                  onChange={e => setClaimSearch(e.target.value)}
                />
                {claimSearch && (
                  <button className="claim-search-clear" onClick={() => setClaimSearch('')}>✕</button>
                )}
              </div>

              <div className="claim-filter-pills">
                <button
                  type="button"
                  className={`filter-pill${claimFilter === 'all' ? ' active' : ''}`}
                  onClick={() => setClaimFilter('all')}
                >
                  All ({realClaims.length})
                </button>
                {realClaims.filter(c => c.verdict?.label === 'true').length > 0 && (
                  <button
                    type="button"
                    className={`filter-pill${claimFilter === 'true' ? ' active' : ''}`}
                    onClick={() => setClaimFilter('true')}
                    style={claimFilter === 'true' ? { background: 'rgba(16,185,129,0.25)', borderColor: '#10b981', color: '#10b981' } : {}}
                  >
                    ✓ True ({realClaims.filter(c => c.verdict?.label === 'true').length})
                  </button>
                )}
                {realClaims.filter(c => c.verdict?.label === 'false').length > 0 && (
                  <button
                    type="button"
                    className={`filter-pill${claimFilter === 'false' ? ' active' : ''}`}
                    onClick={() => setClaimFilter('false')}
                    style={claimFilter === 'false' ? { background: 'rgba(239,68,68,0.25)', borderColor: '#ef4444', color: '#ef4444' } : {}}
                  >
                    ✗ False ({realClaims.filter(c => c.verdict?.label === 'false').length})
                  </button>
                )}
                {realClaims.filter(c => c.verdict?.label === 'misleading').length > 0 && (
                  <button
                    type="button"
                    className={`filter-pill${claimFilter === 'misleading' ? ' active' : ''}`}
                    onClick={() => setClaimFilter('misleading')}
                    style={claimFilter === 'misleading' ? { background: 'rgba(245,158,11,0.25)', borderColor: '#f59e0b', color: '#f59e0b' } : {}}
                  >
                    ⚠ Misleading ({realClaims.filter(c => c.verdict?.label === 'misleading').length})
                  </button>
                )}
              </div>
            </div>
          )}

          {(() => {
            const filtered = realClaims.filter(item => {
              const itemLabel = item.verdict?.label;
              if (claimFilter !== 'all' && itemLabel !== claimFilter) return false;
              if (claimSearch.trim()) {
                const q = claimSearch.toLowerCase();
                const textMatch = item.claim?.normalized_text?.toLowerCase().includes(q) ||
                                  item.claim?.raw_text?.toLowerCase().includes(q);
                const reasoningMatch = item.verdict?.reasoning?.toLowerCase().includes(q) ||
                                       item.verdict?.summary?.toLowerCase().includes(q);
                const sourceMatch = item.verdict?.evidence?.some(e =>
                  e.source_title?.toLowerCase().includes(q) || e.domain?.toLowerCase().includes(q)
                );
                return Boolean(textMatch || reasoningMatch || sourceMatch);
              }
              return true;
            });

            if (filtered.length === 0) {
              return (
                <div style={{ padding: '2.5rem', textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '1.5rem' }}>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '0.75rem' }}>No claims matched your search query or filter.</p>
                  <button
                    type="button"
                    onClick={() => { setClaimFilter('all'); setClaimSearch(''); }}
                    style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid #6366f1', color: '#818cf8', borderRadius: '8px', padding: '0.4rem 1rem', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 700 }}
                  >
                    Clear Filter
                  </button>
                </div>
              );
            }

            return filtered.map((item, i) => (
              <ClaimCard
                key={(item.claim as any).id || i}
                item={item}
                index={i}
                onSeek={handleSeek}
              />
            ));
          })()}
        </div>
      )}

      {/* ── Modals ── */}
      <ExportDossierModal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        jobId={jobId || 'audit-dossier'}
        reportData={{
          videoUrl: url,
          overallVerdict: overallVerdict || 'Unverified',
          category: finalVerdictCategory,
          confidence: overallConfidence,
          breakdown: verdictBreakdown || {},
          claims: realClaims,
          forensics: forensicsReport,
          osint: osintReport,
          dmReport: dmReport,
        }}
      />

      <SystemHealthModal
        isOpen={showHealthModal}
        onClose={() => setShowHealthModal(false)}
      />

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
      {stage !== 'idle' && <MistralCatFooter />}
    </>
  );
}
