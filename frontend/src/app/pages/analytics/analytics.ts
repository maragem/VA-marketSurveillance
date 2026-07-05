import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { EUI_CARD } from '@eui/components/eui-card';
import { ApiService } from '../../core/api.service';
import { AnalyticsData } from '../../core/models';

/** Validated status palette for risk levels (CVD-safe, ≥3:1 on white). */
export const RISK_COLORS: Record<string, string> = {
  compliant: '#467a39',
  low: '#006fb4',
  medium: '#d97706',
  high: '#da2131',
  critical: '#8f2d56',
  unknown: '#9aa7b2',
};

const BAR_HUE = '#004494'; // single-series magnitude bars (EC blue)

@Component({
  selector: 'app-analytics',
  imports: [DatePipe, ...EUI_CARD],
  templateUrl: './analytics.html',
  styleUrl: './analytics.scss',
})
export class AnalyticsPage {
  private readonly api = inject(ApiService);

  protected readonly data = signal<AnalyticsData | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly riskColors = RISK_COLORS;
  protected readonly barHue = BAR_HUE;

  protected readonly maxRisk = computed(() =>
    Math.max(1, ...(this.data()?.risk_distribution.map((r) => r.count) ?? [1])),
  );
  protected readonly maxRegulation = computed(() =>
    Math.max(1, ...(this.data()?.findings_by_regulation.map((r) => r.count) ?? [1])),
  );
  protected readonly maxProvision = computed(() =>
    Math.max(1, ...(this.data()?.top_provisions.map((p) => p.count) ?? [1])),
  );
  protected readonly maxChannel = computed(() =>
    Math.max(1, ...(this.data()?.channels.map((c) => c.count) ?? [1])),
  );
  protected readonly maxDay = computed(() =>
    Math.max(1, ...(this.data()?.timeline.map((d) => d.count) ?? [1])),
  );

  constructor() {
    this.api.analytics().subscribe({
      next: (d) => this.data.set(d),
      error: () => this.error.set('Could not load analytics.'),
    });
  }

  protected pct(count: number, max: number): string {
    return `${Math.max(2, Math.round((100 * count) / max))}%`;
  }

  protected riskLabel(risk: string): string {
    return risk === 'compliant' ? 'no issues' : risk;
  }
}
