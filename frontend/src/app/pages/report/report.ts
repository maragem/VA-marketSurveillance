import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { EuiButtonComponent } from '@eui/components/eui-button';
import { ApiService } from '../../core/api.service';
import { AnalysisReport } from '../../core/models';
import { ReportView } from '../../shared/report-view';

@Component({
  selector: 'app-report',
  imports: [FormsModule, ReportView, RouterLink, EuiButtonComponent],
  template: `
    @if (report(); as r) {
      <div class="bar">
        @if (editing()) {
          <form class="titleedit" (ngSubmit)="saveTitle()">
            <input class="titleedit__input" name="title" [(ngModel)]="draftTitle"
                   maxlength="200" autofocus aria-label="Report title"
                   (keydown.escape)="cancelEdit()" />
            <button euiButton euiPrimary euiSizeS type="submit"
                    [euiDisabled]="!draftTitle.trim() || saving()">
              {{ saving() ? 'Saving…' : 'Save' }}
            </button>
            <button euiButton euiSecondary euiSizeS type="button" (click)="cancelEdit()">Cancel</button>
          </form>
        } @else {
          <h1 class="page-title">
            Compliance report — {{ r.campaign.title }}
            <button class="rename" type="button" (click)="startEdit(r)"
                    title="Rename this report" aria-label="Rename this report">✎</button>
          </h1>
        }
        <span class="bar__actions">
          <a euiButton euiPrimary [href]="'/api/analyses/' + r.id + '/pdf'" download>Download PDF</a>
          <a euiButton euiSecondary routerLink="/analyze" [queryParams]="{ from: r.id }">Fix &amp; re-analyse</a>
          <a euiButton euiSecondary routerLink="/analyze">New analysis</a>
        </span>
      </div>
      @if (renameError()) {
        <p class="rename-error">{{ renameError() }}</p>
      }
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

    .rename {
      border: none;
      background: none;
      cursor: pointer;
      font-size: 1rem;
      color: var(--eui-c-primary, #004494);
      padding: 0 0.25rem;
      vertical-align: middle;

      &:hover {
        opacity: 0.75;
      }
    }

    .titleedit {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex: 1 1 24rem;
      margin: 0 0 1rem;

      &__input {
        flex: 1;
        font-size: 1.1rem;
        padding: 0.35rem 0.6rem;
        border: 1px solid var(--eui-c-neutral-light, #cfd5de);
        border-radius: 4px;
        min-width: 12rem;
      }
    }

    .rename-error {
      color: var(--eui-c-danger, #da2131);
      margin: 0 0 0.75rem;
    }
  `,
})
export class ReportPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);

  protected readonly report = signal<AnalysisReport | null>(null);
  protected readonly notFound = signal(false);
  protected readonly editing = signal(false);
  protected readonly saving = signal(false);
  protected readonly renameError = signal<string | null>(null);
  protected draftTitle = '';

  constructor() {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getAnalysis(id).subscribe({
      next: (r) => this.report.set(r),
      error: () => this.notFound.set(true),
    });
  }

  protected startEdit(r: AnalysisReport): void {
    this.draftTitle = r.campaign.title;
    this.renameError.set(null);
    this.editing.set(true);
  }

  protected cancelEdit(): void {
    this.editing.set(false);
    this.renameError.set(null);
  }

  protected saveTitle(): void {
    const r = this.report();
    const title = this.draftTitle.trim();
    if (!r || !title || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.renameError.set(null);
    this.api.renameAnalysis(r.id, title).subscribe({
      next: (updated) => {
        this.report.set(updated);
        this.saving.set(false);
        this.editing.set(false);
      },
      error: (err) => {
        this.renameError.set(err?.error?.detail ?? 'Could not rename the report.');
        this.saving.set(false);
      },
    });
  }
}
