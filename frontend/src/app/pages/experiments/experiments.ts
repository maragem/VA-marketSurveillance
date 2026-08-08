import { Component, OnDestroy, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ApiService } from '../../core/api.service';
import { ExperimentConfigStatus, ExperimentJob } from '../../core/models';

@Component({
  selector: 'app-experiments',
  imports: [DatePipe],
  templateUrl: './experiments.html',
  styleUrl: './experiments.scss',
})
export class ExperimentsPage implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly timer = setInterval(() => this.refresh(), 5000);

  protected readonly configs = signal<ExperimentConfigStatus[]>([]);
  protected readonly jobs = signal<ExperimentJob[]>([]);
  protected readonly runningJob = signal<string | null>(null);
  protected readonly model = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly starting = signal<string | null>(null);

  constructor() {
    this.refresh();
  }

  ngOnDestroy(): void {
    clearInterval(this.timer);
  }

  protected refresh(): void {
    this.api.experimentsConfigs().subscribe({
      next: (res) => {
        this.configs.set(res.configs);
        this.model.set(res.model);
        this.runningJob.set(res.running_job);
      },
      error: () => undefined,
    });
    this.api.experimentsJobs().subscribe({
      next: (res) => {
        this.jobs.set(res.jobs);
        this.runningJob.set(res.running_job);
      },
      error: () => undefined,
    });
  }

  protected latestJob(configId: string): ExperimentJob | undefined {
    return this.jobs().find((j) => j.config === configId);
  }

  protected start(cfg: ExperimentConfigStatus): void {
    const cost = cfg.id === 'A' ? 'no LLM cost' : `~${cfg.total_analyses} LLM analyses`;
    const ok = confirm(
      `Start configuration ${cfg.id}?\n\n${cfg.cases} cases × ${cfg.runs} runs = ` +
      `${cfg.total_analyses} analyses (${cost}).\n\nThe job runs on the server and survives ` +
      `closing this page; progress is checkpointed after every analysis.`,
    );
    if (!ok) return;
    this.error.set(null);
    this.starting.set(cfg.id);
    this.api.startExperiment(cfg.id).subscribe({
      next: () => {
        this.starting.set(null);
        this.refresh();
      },
      error: (err) => {
        this.starting.set(null);
        this.error.set(err?.error?.detail ?? 'Could not start the experiment.');
      },
    });
  }

  protected cancel(job: ExperimentJob): void {
    if (!confirm(`Cancel ${job.id}? Completed analyses are kept and scored.`)) return;
    this.api.cancelExperiment(job.id).subscribe({
      next: () => this.refresh(),
      error: (err) => this.error.set(err?.error?.detail ?? 'Cancel failed.'),
    });
  }

  protected remove(job: ExperimentJob): void {
    if (!confirm(`Delete ${job.id} and its stored results? Download them first if needed.`)) return;
    this.api.deleteExperiment(job.id).subscribe({
      next: () => this.refresh(),
      error: (err) => this.error.set(err?.error?.detail ?? 'Delete failed.'),
    });
  }

  protected pct(job: ExperimentJob): number {
    return job.total ? Math.round((100 * job.done) / job.total) : 0;
  }

  protected downloadUrl(job: ExperimentJob, kind: 'scorecard' | 'results' | 'reports'): string {
    return `/api/experiments/jobs/${encodeURIComponent(job.id)}/${kind}`;
  }

  protected statusLabel(status: ExperimentJob['status']): string {
    return {
      running: 'Running',
      completed: 'Completed',
      completed_with_errors: 'Completed (with errors)',
      cancelled: 'Cancelled',
      failed: 'Failed',
    }[status];
  }
}
