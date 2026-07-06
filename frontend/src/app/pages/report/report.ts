import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { EuiButtonComponent } from '@eui/components/eui-button';
import { ApiService } from '../../core/api.service';
import { AnalysisReport } from '../../core/models';
import { ReportView } from '../../shared/report-view';

@Component({
  selector: 'app-report',
  imports: [ReportView, RouterLink, EuiButtonComponent],
  template: `
    @if (report(); as r) {
      <div class="bar">
        <h1 class="page-title">Compliance report — {{ r.campaign.title }}</h1>
        <span class="bar__actions">
          <a euiButton euiPrimary [href]="'/api/analyses/' + r.id + '/pdf'" download>Download PDF</a>
          <a euiButton euiSecondary routerLink="/analyze">New analysis</a>
        </span>
      </div>
      <app-report-view [report]="r" />
    } @else if (notFound()) {
      <p>Report not found. <a routerLink="/">Back to dashboard</a></p>
    } @else {
      <p>Loading…</p>
    }
  `,
  styles: `
    .bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
      margin-bottom: 0.5rem;

      &__actions {
        display: flex;
        gap: 0.6rem;
      }
    }

    .page-title {
      font-size: 1.35rem;
      margin: 0 0 1rem;
    }
  `,
})
export class ReportPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);

  protected readonly report = signal<AnalysisReport | null>(null);
  protected readonly notFound = signal(false);

  constructor() {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getAnalysis(id).subscribe({
      next: (r) => this.report.set(r),
      error: () => this.notFound.set(true),
    });
  }
}
