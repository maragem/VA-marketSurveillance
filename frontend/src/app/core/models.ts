export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type Regulation = 'AI_ACT' | 'GDPR' | 'DSA' | 'UCPD';

export interface CampaignSubmission {
  title: string;
  text: string;
  channels: string[];
  target_audience?: string | null;
  markets: string[];
  uses_ai_generation?: boolean | null;
  uses_personalisation?: boolean | null;
  source_platform?: string | null;
  source_url?: string | null;
}

export interface BenchGold {
  compliant: boolean;
  relevant: Regulation[];
  provisions: string[];
  acceptable_extra: string[];
  min_risk: 'critical' | 'high' | 'medium' | 'low' | 'compliant';
}

export interface BenchCase {
  id: string;
  tier: 1 | 2 | 3;
  source: string;
  campaign: CampaignSubmission;
  gold: BenchGold;
}

export interface BenchSummaryRow {
  id: string;
  tier: number;
  compliant_control: boolean;
  run: boolean;
  pass?: boolean;
  engine?: string;
  overall_risk?: string;
  min_risk?: string;
  risk_ok?: boolean;
  matched?: string[];
  missed?: string[];
  unexpected?: string[];
  false_positive?: boolean;
  routing_missed?: string[];
  recorded_at?: string;
}

export interface BenchSummary {
  cases_total: number;
  cases_run: number;
  cases_not_run: string[];
  passed: number;
  failed: number;
  engines: string[];
  latest_run_at: string | null;
  gold_provision_recall: number | null;
  gold_provisions_total: number;
  gold_provisions_matched: number;
  risk_calibration_passed: number;
  routing_missed_total: number;
  unexpected_total: number;
  false_positives_on_controls: number;
  controls_run: number;
  top_unexpected: { provision_id: string; ref: string; count: number }[];
  top_missed: { provision_id: string; ref: string; count: number }[];
  cases: BenchSummaryRow[];
}

export interface CalibrationRule {
  id: string;
  rule: string;
  origin?: string;
}

export type Calibration = Record<string, CalibrationRule[]>;

export interface LessonProposal {
  regulation: string;
  rule: string;
  why: string;
  evidence_case_ids: string[];
}

export interface BenchAdjudication {
  verdict: 'must_find' | 'acceptable_extra' | 'reject';
  confidence: 'high' | 'medium' | 'low';
  reasoning: string;
}

export interface BenchUnexpectedFinding {
  id: string;
  severity: string;
  rationale?: string;
  evidence_quote?: string | null;
  adjudication?: BenchAdjudication;
}

/** Stored gold-vs-run comparison for a benchmark case (mirrors bench/run.py scoring). */
export interface BenchRunOutcome {
  engine: string;
  overallRisk: string;
  riskOk: boolean;
  compliantControl: boolean;
  falsePositive: boolean;
  routed: string[];
  routingMissed: string[];
  routingExtra: string[];
  matched: string[];
  missed: string[];
  unexpected: BenchUnexpectedFinding[];
  pass: boolean;
  recorded_at?: string;
}

export interface YouTubeSearchResult {
  video_id: string;
  url: string;
  title: string;
  channel: string;
  views: string;
  published: string;
  length: string;
  description: string;
  thumbnail: string;
}

export interface YouTubeVideoBundle {
  video_id: string;
  url: string;
  title: string;
  channel: string;
  description: string;
  transcript: string;
}

export interface Finding {
  regulation: Regulation;
  provision_id: string;
  provision_ref: string;
  title: string;
  severity: Severity;
  rationale: string;
  evidence_quote?: string | null;
  recommendation: string;
  graph_path: string[];
  celex?: string | null;
  source_url?: string | null;
}

export interface TriageResult {
  detected_practices: string[];
  audience_notes?: string | null;
  ai_involved: boolean;
  personal_data_involved: boolean;
  minors_potentially_reached: boolean;
  regulations_to_check: Regulation[];
  summary: string;
}

export type VerdictStatus =
  | 'violation_likely'
  | 'risk_identified'
  | 'attention'
  | 'compliant'
  | 'not_applicable';

export interface RegulationVerdict {
  regulation: Regulation;
  status: VerdictStatus;
  findings: Finding[];
  notes: string;
}

export interface AnalysisReport {
  id: string;
  created_at: string;
  parent_id?: string | null;
  campaign: CampaignSubmission;
  triage?: TriageResult | null;
  verdicts: RegulationVerdict[];
  overall_risk: 'critical' | 'high' | 'medium' | 'low' | 'compliant' | 'unknown';
  executive_summary: string;
  recommendations: string[];
  engine: 'agentic' | 'heuristic';
  status: 'pending' | 'running' | 'completed' | 'failed';
  error?: string | null;
}

export interface AnalysisListItem {
  id: string;
  created_at: string;
  overall_risk: string;
  status: string;
  title: string;
}

export interface GraphNode {
  id: string;
  type: 'regulation' | 'provision' | 'concept';
  regulation?: string | null;
  ref?: string | null;
  title?: string | null;
  severity_hint?: string | null;
  text?: string | null;
  source?: {
    celex?: string;
    eli?: string;
    cellar_uri?: string;
    eur_lex_url?: string;
  } | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  note?: string | null;
}

export interface GraphFull {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DiffFinding extends Finding {
  previous_severity?: Severity;
}

export interface AnalysisDiff {
  parent: { id: string; created_at: string; overall_risk: string; findings: number };
  current: { id: string; created_at: string; overall_risk: string; findings: number };
  resolved: DiffFinding[];
  remaining: DiffFinding[];
  new: DiffFinding[];
}

export interface CellarMetadata {
  celex: string;
  available: boolean;
  cellar_work?: string | null;
  title?: string | null;
  date_document?: string | null;
}

export interface AnalyticsData {
  totals: {
    reports: number;
    findings: number;
    high_or_critical_pct: number;
    agentic_pct: number;
  };
  risk_distribution: { risk: string; count: number }[];
  findings_by_regulation: {
    regulation: string;
    label: string;
    count: number;
    severities: Record<string, number>;
  }[];
  top_provisions: { ref: string; title: string; count: number }[];
  timeline: { date: string; count: number; high: number }[];
  channels: { channel: string; count: number; high: number }[];
}

export interface StreamEvent {
  type: string;
  [key: string]: unknown;
}

export const REGULATION_LABELS: Record<Regulation, string> = {
  AI_ACT: 'AI Act',
  GDPR: 'GDPR',
  DSA: 'Digital Services Act',
  UCPD: 'Unfair Commercial Practices',
};
