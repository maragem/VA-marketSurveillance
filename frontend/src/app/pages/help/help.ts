import { Component, inject, signal } from '@angular/core';
import { ApiService } from '../../core/api.service';

interface TocEntry {
  id: string;
  label: string;
}

@Component({
  selector: 'app-help',
  templateUrl: './help.html',
  styleUrl: './help.scss',
})
export class HelpPage {
  private readonly api = inject(ApiService);

  protected readonly engine = signal<'agentic' | 'heuristic' | null>(null);

  protected readonly toc: TocEntry[] = [
    { id: 'about', label: 'What this tool is' },
    { id: 'quickstart', label: 'Quick start' },
    { id: 'pipeline', label: 'How an analysis works' },
    { id: 'report', label: 'Reading a report' },
    { id: 'youtube', label: 'YouTube surveillance' },
    { id: 'dashboard', label: 'Dashboard & analytics' },
    { id: 'graph', label: 'Knowledge graph' },
    { id: 'benchmark', label: 'Benchmark' },
    { id: 'experiments', label: 'Experiments' },
    { id: 'reference', label: 'Severity & status reference' },
    { id: 'disclaimer', label: 'Data handling & disclaimer' },
  ];

  constructor() {
    this.api.health().subscribe({
      next: (h) => this.engine.set(h.llm_configured ? 'agentic' : 'heuristic'),
      error: () => this.engine.set(null),
    });
  }

  protected scrollTo(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
