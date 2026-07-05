import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { EUI_BADGE } from '@eui/components/eui-badge';
import { EuiButtonComponent } from '@eui/components/eui-button';
import { EUI_CARD } from '@eui/components/eui-card';
import { ApiService } from '../../core/api.service';
import { AnalysisListItem } from '../../core/models';

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, RouterLink, EuiButtonComponent, ...EUI_CARD, ...EUI_BADGE],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class DashboardPage {
  private readonly api = inject(ApiService);

  protected readonly analyses = signal<AnalysisListItem[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.api.listAnalyses().subscribe({
      next: (items) => {
        this.analyses.set(items);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load previous analyses.');
        this.loading.set(false);
      },
    });
  }

  riskIsDanger(risk: string): boolean {
    return risk === 'critical' || risk === 'high';
  }

  riskIsWarning(risk: string): boolean {
    return risk === 'medium';
  }

  riskIsOk(risk: string): boolean {
    return risk === 'low' || risk === 'compliant';
  }
}
