import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  AnalysisDiff,
  AnalysisListItem,
  AnalysisReport,
  AnalyticsData,
  BenchAdjudication,
  BenchCase,
  BenchRunOutcome,
  BenchSummary,
  Calibration,
  CalibrationRule,
  CampaignSubmission,
  LessonProposal,
  CellarMetadata,
  GraphFull,
  StreamEvent,
  YouTubeSearchResult,
  YouTubeVideoBundle,
} from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  health(): Observable<{ status: string; llm_configured: boolean; model: string | null }> {
    return this.http.get<{ status: string; llm_configured: boolean; model: string | null }>(
      `${this.base}/health`,
    );
  }

  listAnalyses(): Observable<AnalysisListItem[]> {
    return this.http.get<AnalysisListItem[]>(`${this.base}/analyses`);
  }

  getAnalysis(id: string): Observable<AnalysisReport> {
    return this.http.get<AnalysisReport>(`${this.base}/analyses/${id}`);
  }

  renameAnalysis(id: string, title: string): Observable<AnalysisReport> {
    return this.http.patch<AnalysisReport>(`${this.base}/analyses/${id}`, { title });
  }

  cellarMetadata(celex: string): Observable<CellarMetadata> {
    return this.http.get<CellarMetadata>(`${this.base}/cellar/${celex}`);
  }

  analytics(): Observable<AnalyticsData> {
    return this.http.get<AnalyticsData>(`${this.base}/analytics`);
  }

  graphFull(): Observable<GraphFull> {
    return this.http.get<GraphFull>(`${this.base}/graph/full`);
  }

  getDiff(id: string): Observable<AnalysisDiff> {
    return this.http.get<AnalysisDiff>(`${this.base}/analyses/${id}/diff`);
  }

  benchCases(): Observable<{ cases: BenchCase[] }> {
    return this.http.get<{ cases: BenchCase[] }>(`${this.base}/bench/cases`);
  }

  createBenchCase(benchCase: BenchCase): Observable<BenchCase> {
    return this.http.post<BenchCase>(`${this.base}/bench/cases`, benchCase);
  }

  updateBenchCase(benchCase: BenchCase): Observable<BenchCase> {
    return this.http.put<BenchCase>(`${this.base}/bench/cases/${encodeURIComponent(benchCase.id)}`, benchCase);
  }

  deleteBenchCase(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/bench/cases/${encodeURIComponent(id)}`);
  }

  benchSummary(): Observable<BenchSummary> {
    return this.http.get<BenchSummary>(`${this.base}/bench/summary`);
  }

  calibration(): Observable<Calibration> {
    return this.http.get<Calibration>(`${this.base}/calibration`);
  }

  addCalibrationRule(regulation: string, rule: string, origin: string): Observable<CalibrationRule> {
    return this.http.post<CalibrationRule>(`${this.base}/calibration/rules`, { regulation, rule, origin });
  }

  deleteCalibrationRule(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/calibration/rules/${encodeURIComponent(id)}`);
  }

  proposeLessons(): Observable<{ proposals: LessonProposal[] }> {
    return this.http.post<{ proposals: LessonProposal[] }>(`${this.base}/bench/lessons/propose`, {});
  }

  adjudicateFinding(campaign: CampaignSubmission, finding: {
    provision_id: string; severity: string; rationale?: string; evidence_quote?: string | null;
  }): Observable<BenchAdjudication> {
    return this.http.post<BenchAdjudication>(`${this.base}/bench/adjudicate`, {
      campaign,
      provision_id: finding.provision_id,
      severity: finding.severity,
      rationale: finding.rationale ?? '',
      evidence_quote: finding.evidence_quote ?? null,
    });
  }

  benchRuns(): Observable<Record<string, BenchRunOutcome>> {
    return this.http.get<Record<string, BenchRunOutcome>>(`${this.base}/bench/runs`);
  }

  saveBenchRun(id: string, outcome: BenchRunOutcome): Observable<BenchRunOutcome> {
    return this.http.put<BenchRunOutcome>(`${this.base}/bench/runs/${encodeURIComponent(id)}`, outcome);
  }

  youtubeSearch(q: string, uploadDate?: string, sortBy?: string): Observable<YouTubeSearchResult[]> {
    let params = new HttpParams().set('q', q);
    if (uploadDate) {
      params = params.set('upload_date', uploadDate);
    }
    if (sortBy) {
      params = params.set('sort_by', sortBy);
    }
    return this.http.get<YouTubeSearchResult[]>(`${this.base}/youtube/search`, { params });
  }

  youtubeVideo(videoId: string, language?: string): Observable<YouTubeVideoBundle> {
    let params = new HttpParams();
    if (language && language !== 'auto') {
      params = params.set('language', language);
    }
    return this.http.get<YouTubeVideoBundle>(`${this.base}/youtube/videos/${videoId}`, { params });
  }

  /**
   * POST the campaign and consume the SSE progress stream from the response
   * body (EventSource cannot POST, so events are parsed off a fetch stream).
   */
  async analyzeStream(
    campaign: CampaignSubmission,
    onEvent: (event: StreamEvent) => void,
    parentId?: string | null,
    signal?: AbortSignal,
    persist = true,
  ): Promise<void> {
    const params = new URLSearchParams();
    if (parentId) {
      params.set('parent_id', parentId);
    }
    if (!persist) {
      params.set('persist', 'false');
    }
    const query = params.size ? `?${params.toString()}` : '';
    const response = await fetch(`${this.base}/analyses/stream${query}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(campaign),
      signal,
    });
    if (!response.ok || !response.body) {
      throw new Error(`Analysis request failed (HTTP ${response.status})`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const chunk = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            onEvent(JSON.parse(line.slice(6)) as StreamEvent);
          }
        }
      }
    }
  }
}
