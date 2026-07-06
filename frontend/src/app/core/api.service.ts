import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  AnalysisDiff,
  AnalysisListItem,
  AnalysisReport,
  AnalyticsData,
  CampaignSubmission,
  CellarMetadata,
  GraphFull,
  StreamEvent,
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

  /**
   * POST the campaign and consume the SSE progress stream from the response
   * body (EventSource cannot POST, so events are parsed off a fetch stream).
   */
  async analyzeStream(
    campaign: CampaignSubmission,
    onEvent: (event: StreamEvent) => void,
    parentId?: string | null,
    signal?: AbortSignal,
  ): Promise<void> {
    const query = parentId ? `?parent_id=${encodeURIComponent(parentId)}` : '';
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
