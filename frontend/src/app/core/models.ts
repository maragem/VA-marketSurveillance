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

export interface CellarMetadata {
  celex: string;
  available: boolean;
  cellar_work?: string | null;
  title?: string | null;
  date_document?: string | null;
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
