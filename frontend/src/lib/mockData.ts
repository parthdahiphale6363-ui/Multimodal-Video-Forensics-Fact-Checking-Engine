// Types and full mock data for the advanced fact-checker demo

export type SourcePlatform = 'youtube' | 'instagram' | 'facebook';
export type VerdictLabel = 'true' | 'false' | 'misleading';
export type DomainTrust = 'high' | 'medium' | 'low' | 'blocked';
export type CheckStatus = 'pass' | 'fail' | 'warn' | 'neutral';

export interface Evidence {
  source_url: string;
  source_title: string;
  domain: string;
  domain_trust: DomainTrust;
  snippet: string;
  relevance_score: number;
  publication_date: string;
  supports_claim: boolean;
  stance?: 'supports' | 'contradicts' | 'mixed' | 'irrelevant' | 'insufficient';
  is_independent?: boolean;
  explanation?: string;
  relevant_passage?: string;
  quote?: string;
  quote_location?: string;
  quote_verified?: boolean;
  publisher?: string;
  retrieval_timestamp?: string;
  credibility_limitation?: string;
}

export interface SearchRun {
  query: string;
  source_type: string;
  results_found: number;
  top_domain: string;
  trust_level: DomainTrust;
  stance: 'contradicts' | 'supports' | 'mixed' | 'neutral' | 'irrelevant' | 'insufficient';
}

export interface LLMCheck {
  agent: string;
  role: string;
  finding: string;
  passed: boolean;
}

export interface FactCheckSummary {
  searches_run: number;
  sources_found: number;
  sources_accepted: number;
  sources_blocked: number;
  consensus_score: number;        // 0-1, how much sources agree
  cross_platform_hits: number;
  llm_rounds: number;
  critic_rejections: number;
}

export interface AtomicClaimAssessment {
  id: string;
  atomic_claim: string;
  verdict: VerdictLabel;
  reasoning: string;
  confidence: number;
  supporting_quote_ids?: string[];
  contradicting_quote_ids?: string[];
}

export interface Claim {
  id: string;
  source_video_id: string;
  source_platform: SourcePlatform;
  raw_text: string;
  normalized_text: string;
  language: string;
  timestamp_in_video: number;
  embedding_id: string | null;
  created_at: string;
}

export interface Verdict {
  id: string;
  claim_id: string;
  label: VerdictLabel;
  confidence: number;
  evidence: Evidence[];
  reasoning: string;
  summary: string;
  search_runs: SearchRun[];
  llm_checks: LLMCheck[];
  fact_check_summary: FactCheckSummary;
  atomic_assessments?: AtomicClaimAssessment[];
  canonical_hash?: string;
  unresolved_uncertainties?: string[];
  created_at: string;
}

export interface ClaimWithVerdict {
  claim: Claim;
  verdict: Verdict;
  related_count: number;
  related_platforms: string[];
}

export interface TranscriptSegment {
  text: string;
  start: number;
  end: number;
}

// ── Utility helpers ────────────────────────────────────────────────────────────
export function getYouTubeId(url: string): string | null {
  const patterns = [
    /[?&]v=([^&#]+)/,
    /youtu\.be\/([^?&#]+)/,
    /youtube\.com\/shorts\/([^?&#]+)/,
    /youtube\.com\/embed\/([^?&#]+)/,
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return null;
}

export function detectPlatform(url: string): SourcePlatform {
  if (url.includes('youtu')) return 'youtube';
  if (url.includes('instagram')) return 'instagram';
  if (url.includes('facebook') || url.includes('fb.com')) return 'facebook';
  return 'youtube';
}

// ── Mock Transcript ────────────────────────────────────────────────────────────
export const mockTranscriptSegments: TranscriptSegment[] = [
  { text: "Welcome back everyone. Today we're going to talk about some amazing health breakthroughs.", start: 0, end: 4.2 },
  { text: "Scientists have confirmed that drinking lemon water every day completely cures all known diseases.", start: 4.3, end: 9.1 },
  { text: "In fact, a Harvard study from last month showed that patients recovered from cancer just by drinking lemon juice.", start: 9.2, end: 15.8 },
  { text: "Also, the economy completely collapsed yesterday and millions are now unemployed.", start: 16.0, end: 21.3 },
  { text: "I personally think this is the most important thing you'll hear all year.", start: 21.4, end: 25.0 },
  { text: "Governments around the world are reportedly hiding this data from the public.", start: 25.1, end: 30.2 },
  { text: "The WHO confirmed in their latest briefing that over 5 billion people have been affected.", start: 30.3, end: 36.5 },
];

// ── Simulated Search Feed ──────────────────────────────────────────────────────
export const mockSearchQueries = [
  { query: '"lemon water cures all diseases" clinical evidence', source: 'PubMed Central', claim_idx: 0 },
  { query: '"lemon water cancer cure" harvard medical school 2026', source: 'Harvard Health Publishing', claim_idx: 0 },
  { query: 'lemon water disease cure WHO CDC factual review', source: 'WHO / CDC', claim_idx: 0 },
  { query: 'citrus juice cancer remission systematic review', source: 'The Lancet', claim_idx: 0 },
  { query: 'lemon water immunity claims fact check site:reuters.com', source: 'Reuters Fact Check', claim_idx: 0 },
  { query: '"economy collapsed" global GDP June 2026 site:reuters.com', source: 'Reuters Economics', claim_idx: 1 },
  { query: 'global unemployment statistics IMF June 2026', source: 'IMF World Economic Outlook', claim_idx: 1 },
  { query: '"economy collapse" 2026 Bloomberg AP news analysis', source: 'Bloomberg / AP', claim_idx: 1 },
  { query: 'WHO 5 billion affected briefing 2026 site:who.int', source: 'WHO.int Official', claim_idx: 2 },
  { query: '"5 billion people" WHO press release June 2026', source: 'UN News', claim_idx: 2 },
  { query: 'WHO global health statistics 2026 population affected', source: 'Our World in Data', claim_idx: 2 },
];

// ── Full Verified Results ──────────────────────────────────────────────────────
export const mockClaimsWithVerdicts: ClaimWithVerdict[] = [
  // ─── CLAIM 1 ───────────────────────────────────────────────────────────────
  {
    claim: {
      id: "c1111111-1111-1111-1111-111111111111",
      source_video_id: "demo_video",
      source_platform: "youtube",
      raw_text: "Drinking lemon water every day completely cures all known diseases. A Harvard study showed patients recovered from cancer by drinking lemon juice.",
      normalized_text: "Daily lemon water consumption cures all known diseases, including cancer, per a Harvard study.",
      language: "en",
      timestamp_in_video: 4.3,
      embedding_id: "emb_001",
      created_at: new Date().toISOString()
    },
    verdict: {
      id: "v1",
      claim_id: "c1111111-1111-1111-1111-111111111111",
      label: "false",
      confidence: 0.98,
      summary: "No credible scientific or medical source supports the claim that lemon water cures any disease, let alone all diseases or cancer. The alleged Harvard study does not exist.",
      reasoning: "5 independent searches across PubMed, Harvard Health, WHO, The Lancet, and Reuters all unanimously contradict this claim. A systematic review of 47 studies found no curative effect of citrus juice. The Harvard study referenced does not appear in any academic database. The Critic Agent flagged the initial draft as insufficiently firm and demanded a final Lancet citation to reach consensus.",
      evidence: [
        {
          source_url: "https://www.health.harvard.edu/staying-healthy/is-lemon-water-a-miracle-cure",
          source_title: "Is lemon water a 'miracle cure'? — Harvard Health",
          domain: "health.harvard.edu",
          domain_trust: "high",
          snippet: "While lemon water provides Vitamin C and helps with hydration, there is absolutely no scientific evidence that it cures diseases. Claims of it curing cancer are completely unfounded and potentially dangerous as they discourage evidence-based treatment.",
          relevance_score: 0.98,
          publication_date: "2025-03-12",
          supports_claim: false
        },
        {
          source_url: "https://pubmed.ncbi.nlm.nih.gov/38291048/",
          source_title: "Citrus Fruits and Cancer Risk: A Systematic Review — PubMed",
          domain: "pubmed.ncbi.nlm.nih.gov",
          domain_trust: "high",
          snippet: "Systematic review of 47 randomized controlled trials found no evidence supporting citrus juice as a curative agent for any form of cancer. Some antioxidant benefit was noted but no therapeutic efficacy.",
          relevance_score: 0.96,
          publication_date: "2024-11-05",
          supports_claim: false
        },
        {
          source_url: "https://www.who.int/news-room/fact-sheets/detail/cancer",
          source_title: "Cancer Fact Sheet — World Health Organization",
          domain: "who.int",
          domain_trust: "high",
          snippet: "Cancer treatment requires evidence-based medical interventions including surgery, chemotherapy, immunotherapy, and targeted therapies. No food or beverage has been proven to cure cancer.",
          relevance_score: 0.94,
          publication_date: "2024-09-01",
          supports_claim: false
        },
        {
          source_url: "https://www.thelancet.com/journals/lanonc/article/PIIS1470-2045(24)00391-9",
          source_title: "Fruit Juice Interventions in Oncology: Evidence Review — The Lancet Oncology",
          domain: "thelancet.com",
          domain_trust: "high",
          snippet: "A rigorous review of 120 clinical studies found zero statistical basis for fruit juice as a primary cancer treatment. Authors warn against patient harm from abandoning conventional therapy.",
          relevance_score: 0.97,
          publication_date: "2024-08-15",
          supports_claim: false
        },
        {
          source_url: "https://reuters.com/fact-check/lemon-water-cure-2026",
          source_title: "FACT CHECK: Does lemon water cure diseases? — Reuters Fact Check",
          domain: "reuters.com",
          domain_trust: "high",
          snippet: "Reuters Fact Check rating: FALSE. No credible scientific evidence exists. No Harvard study matching this description was found in PubMed, Google Scholar, or Harvard's publication archive.",
          relevance_score: 0.99,
          publication_date: "2026-06-15",
          supports_claim: false
        }
      ],
      search_runs: [
        { query: '"lemon water cures disease" clinical evidence', source_type: 'Academic Database', results_found: 142, top_domain: 'pubmed.ncbi.nlm.nih.gov', trust_level: 'high', stance: 'contradicts' },
        { query: '"Harvard lemon juice cancer" 2025 2026', source_type: 'University Research', results_found: 0, top_domain: 'scholar.google.com', trust_level: 'high', stance: 'irrelevant' },
        { query: 'lemon water cancer cure WHO CDC factcheck', source_type: 'Health Authority', results_found: 38, top_domain: 'who.int', trust_level: 'high', stance: 'contradicts' },
        { query: 'citrus juice cancer systematic review Lancet', source_type: 'Peer-Reviewed Journal', results_found: 91, top_domain: 'thelancet.com', trust_level: 'high', stance: 'contradicts' },
        { query: 'lemon water disease cure reuters fact check', source_type: 'Fact-Check Service', results_found: 17, top_domain: 'reuters.com', trust_level: 'high', stance: 'contradicts' },
      ],
      llm_checks: [
        { agent: 'Researcher Agent (Run 1)', role: 'Initial fact-finding', finding: 'Claim is FALSE. No scientific basis. No matching Harvard study found in any academic database.', passed: true },
        { agent: 'Critic Agent', role: 'Evidence quality review', finding: 'Initial evidence accepted but requested one additional peer-reviewed citation from The Lancet to solidify consensus.', passed: false },
        { agent: 'Researcher Agent (Run 2)', role: 'Supplementary search', finding: 'Lancet Oncology systematic review retrieved. Adds strong peer-reviewed confirmation.', passed: true },
        { agent: 'Critic Agent (Final)', role: 'Final verdict approval', finding: '5 high-trust sources all contradict the claim. No supporting source found. Verdict confirmed: FALSE at 98% confidence.', passed: true },
      ],
      fact_check_summary: {
        searches_run: 5,
        sources_found: 288,
        sources_accepted: 5,
        sources_blocked: 12,
        consensus_score: 1.0,
        cross_platform_hits: 14,
        llm_rounds: 2,
        critic_rejections: 1,
      },
      created_at: new Date().toISOString()
    },
    related_count: 14,
    related_platforms: ['instagram', 'facebook', 'youtube']
  },
  // ─── CLAIM 2 ───────────────────────────────────────────────────────────────
  {
    claim: {
      id: "c2222222-2222-2222-2222-222222222222",
      source_video_id: "demo_video",
      source_platform: "youtube",
      raw_text: "The economy completely collapsed yesterday and millions are now unemployed.",
      normalized_text: "The global economy completely collapsed in June 2026, causing mass unemployment.",
      language: "en",
      timestamp_in_video: 16.0,
      embedding_id: "emb_002",
      created_at: new Date().toISOString()
    },
    verdict: {
      id: "v2",
      claim_id: "c2222222-2222-2222-2222-222222222222",
      label: "false",
      confidence: 0.95,
      summary: "Major economic indicators from the IMF, Reuters, and Bloomberg all show stable global economic conditions in June 2026. No market collapse or mass unemployment event occurred.",
      reasoning: "Three separate searches across Reuters, IMF data, and Bloomberg/AP found no evidence of a global economic collapse in June 2026. IMF projects 3.1% GDP growth. Unemployment figures from the OECD show globally stable rates of 5.1%. The claim is wholly fabricated.",
      evidence: [
        {
          source_url: "https://www.reuters.com/markets/global-markets-roundup-2026-06-27/",
          source_title: "Global Markets Roundup — Reuters, June 27 2026",
          domain: "reuters.com",
          domain_trust: "high",
          snippet: "Global markets closed mixed on June 27, 2026, with no indication of systemic collapse. S&P 500 and Dow Jones both remained within 1.5% of all-time highs. IMF forecasts remain at 3.1% growth.",
          relevance_score: 0.97,
          publication_date: "2026-06-27",
          supports_claim: false
        },
        {
          source_url: "https://www.imf.org/en/Publications/WEO/Issues/2026/06/",
          source_title: "World Economic Outlook June 2026 — IMF",
          domain: "imf.org",
          domain_trust: "high",
          snippet: "Global GDP growth projected at 3.1% for 2026. Emerging markets growing at 4.8%. No major economy is in recession. Employment conditions remain robust.",
          relevance_score: 0.95,
          publication_date: "2026-06-01",
          supports_claim: false
        },
        {
          source_url: "https://www.bloomberg.com/news/articles/2026-06-28/economy-outlook",
          source_title: "Global Economy Outlook: Stable Despite Uncertainty — Bloomberg",
          domain: "bloomberg.com",
          domain_trust: "high",
          snippet: "Despite ongoing geopolitical pressures, global economic fundamentals remain sound. Unemployment in G7 countries averaged 4.3% in May 2026, near historic lows.",
          relevance_score: 0.93,
          publication_date: "2026-06-28",
          supports_claim: false
        }
      ],
      search_runs: [
        { query: '"economy collapsed" global June 2026 site:reuters.com', source_type: 'Newswire', results_found: 0, top_domain: 'reuters.com', trust_level: 'high', stance: 'contradicts' },
        { query: 'global unemployment statistics IMF June 2026', source_type: 'Economic Authority', results_found: 54, top_domain: 'imf.org', trust_level: 'high', stance: 'contradicts' },
        { query: '"economic collapse" 2026 bloomberg AP news analysis', source_type: 'Financial Media', results_found: 23, top_domain: 'bloomberg.com', trust_level: 'high', stance: 'contradicts' },
      ],
      llm_checks: [
        { agent: 'Researcher Agent (Run 1)', role: 'Initial fact-finding', finding: 'No evidence of economic collapse found. IMF and Reuters data contradict the claim entirely.', passed: true },
        { agent: 'Critic Agent', role: 'Evidence quality review', finding: 'Evidence is sufficient. Verdict confirmed: FALSE. No critic rejection needed.', passed: true },
      ],
      fact_check_summary: {
        searches_run: 3,
        sources_found: 77,
        sources_accepted: 3,
        sources_blocked: 4,
        consensus_score: 1.0,
        cross_platform_hits: 7,
        llm_rounds: 1,
        critic_rejections: 0,
      },
      created_at: new Date().toISOString()
    },
    related_count: 7,
    related_platforms: ['facebook', 'instagram']
  },
  // ─── CLAIM 3 ───────────────────────────────────────────────────────────────
  {
    claim: {
      id: "c3333333-3333-3333-3333-333333333333",
      source_video_id: "demo_video",
      source_platform: "youtube",
      raw_text: "The WHO confirmed over 5 billion people have been affected.",
      normalized_text: "The WHO confirmed in 2026 that over 5 billion people were affected by an unnamed health event.",
      language: "en",
      timestamp_in_video: 30.3,
      embedding_id: "emb_003",
      created_at: new Date().toISOString()
    },
    verdict: {
      id: "v3",
      claim_id: "c3333333-3333-3333-3333-333333333333",
      label: "misleading",
      confidence: 0.82,
      summary: "No WHO publication from 2026 contains a statement about '5 billion people affected'. The claim is likely fabricated or severely misattributed, but cannot be definitively falsified without knowing which condition is referenced.",
      reasoning: "Three searches against WHO.int, UN News, and Our World in Data found no press release or briefing matching this description. The extreme vagueness of 'affected' makes full falsification impossible — hence 'unverifiable' rather than 'false'. The Critic Agent marked this as high-risk misinformation due to the implausibility of the number.",
      evidence: [
        {
          source_url: "https://www.who.int/emergencies/situations/",
          source_title: "WHO Active Emergency Situations — WHO.int",
          domain: "who.int",
          domain_trust: "high",
          snippet: "WHO's official emergency tracker for June 2026 lists 13 active events. None involve 5 billion people. The largest active event (mpox) affects an estimated 1.2 million people.",
          relevance_score: 0.9,
          publication_date: "2026-06-28",
          supports_claim: false
        },
        {
          source_url: "https://news.un.org/en/story/2026/06/",
          source_title: "UN News — June 2026 Health Briefings",
          domain: "news.un.org",
          domain_trust: "high",
          snippet: "UN News published no report of a WHO announcement regarding 5 billion affected individuals in June 2026.",
          relevance_score: 0.82,
          publication_date: "2026-06-25",
          supports_claim: false
        }
      ],
      search_runs: [
        { query: 'WHO "5 billion" affected briefing June 2026', source_type: 'International Authority', results_found: 0, top_domain: 'who.int', trust_level: 'high', stance: 'irrelevant' },
        { query: '"5 billion people" WHO press release 2026', source_type: 'News Aggregator', results_found: 3, top_domain: 'news.un.org', trust_level: 'high', stance: 'neutral' },
        { query: 'WHO global health statistics affected population 2026', source_type: 'Data Repository', results_found: 41, top_domain: 'ourworldindata.org', trust_level: 'high', stance: 'neutral' },
      ],
      llm_checks: [
        { agent: 'Researcher Agent (Run 1)', role: 'Initial fact-finding', finding: 'No matching WHO statement found. Claim appears fabricated but cannot be fully falsified due to ambiguity of "affected".', passed: true },
        { agent: 'Critic Agent', role: 'Evidence quality review', finding: 'Agreed. The statistical implausibility of the figure (62% of world population) combined with zero traceable source warrants UNVERIFIABLE rating with high misinformation risk flag.', passed: true },
      ],
      fact_check_summary: {
        searches_run: 3,
        sources_found: 44,
        sources_accepted: 2,
        sources_blocked: 2,
        consensus_score: 0.87,
        cross_platform_hits: 3,
        llm_rounds: 1,
        critic_rejections: 0,
      },
      created_at: new Date().toISOString()
    },
    related_count: 3,
    related_platforms: ['youtube']
  }
];

export const mockRelatedClaims: Record<string, Claim[]> = {
  "c1111111-1111-1111-1111-111111111111": [
    {
      id: "related_1",
      source_video_id: "ig_vid_777",
      source_platform: "instagram",
      raw_text: "El agua con limón cura el cáncer completamente.",
      normalized_text: "Lemon water completely cures cancer.",
      language: "es",
      timestamp_in_video: 22.0,
      embedding_id: "emb_r1",
      created_at: "2026-06-25T12:00:00Z"
    },
    {
      id: "related_2",
      source_video_id: "fb_vid_234",
      source_platform: "facebook",
      raw_text: "Doctors HATE this: lemon juice cures everything!",
      normalized_text: "Lemon juice cures all diseases.",
      language: "en",
      timestamp_in_video: 5.1,
      embedding_id: "emb_r2",
      created_at: "2026-06-27T08:30:00Z"
    }
  ]
};
