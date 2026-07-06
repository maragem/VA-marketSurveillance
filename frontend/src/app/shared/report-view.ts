import { Component, effect, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { EUI_ALERT } from '@eui/components/eui-alert';
import { EUI_BADGE } from '@eui/components/eui-badge';
import { EUI_CARD } from '@eui/components/eui-card';
import { EUI_CHIP } from '@eui/components/eui-chip';
import { ApiService } from '../core/api.service';
import {
  AnalysisDiff,
  AnalysisReport,
  CellarMetadata,
  Finding,
  REGULATION_LABELS,
  Regulation,
  RegulationVerdict,
  Severity,
} from '../core/models';

export interface SourceRow {
  celex: string;
  regulations: string[];
  eurLexUrl: string;
  cellar: CellarMetadata | null; // null = lookup in flight
}

@Component({
  selector: 'app-report-view',
  imports: [DatePipe, ...EUI_CARD, ...EUI_ALERT, ...EUI_BADGE, ...EUI_CHIP],
  templateUrl: './report-view.html',
  styleUrl: './report-view.scss',
})
export class ReportView {
  private readonly api = inject(ApiService);

  readonly report = input.required<AnalysisReport>();
  readonly sources = signal<SourceRow[]>([]);
  readonly diff = signal<AnalysisDiff | null>(null);

  readonly regulationLabels = REGULATION_LABELS;

  constructor() {
    // Collect the distinct CELEX numbers cited by the report's findings and
    // look each one up live in CELLAR (official title, date, work URI).
    // Re-analyses get a resolved/remaining/new diff against their parent.
    effect(() => {
      const r = this.report();
      this.diff.set(null);
      if (r.parent_id) {
        this.api.getDiff(r.id).subscribe({
          next: (d) => this.diff.set(d),
          error: () => this.diff.set(null),
        });
      }
    });

    effect(() => {
      const r = this.report();
      const byCelex = new Map<string, SourceRow>();
      for (const verdict of r.verdicts) {
        for (const finding of verdict.findings) {
          if (!finding.celex) {
            continue;
          }
          const row = byCelex.get(finding.celex) ?? {
            celex: finding.celex,
            regulations: [],
            eurLexUrl: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${finding.celex}`,
            cellar: null,
          };
          const label = this.regulationLabel(verdict.regulation);
          if (!row.regulations.includes(label)) {
            row.regulations.push(label);
          }
          byCelex.set(finding.celex, row);
        }
      }
      const rows = [...byCelex.values()];
      this.sources.set(rows);
      for (const row of rows) {
        this.api.cellarMetadata(row.celex).subscribe({
          next: (meta) => this.patchSource(row.celex, meta),
          error: () => this.patchSource(row.celex, { celex: row.celex, available: false }),
        });
      }
    });
  }

  private patchSource(celex: string, meta: CellarMetadata): void {
    this.sources.update((rows) =>
      rows.map((row) => (row.celex === celex ? { ...row, cellar: meta } : row)),
    );
  }

  regulationLabel(reg: Regulation): string {
    return this.regulationLabels[reg] ?? reg;
  }

  riskLabel(risk: string): string {
    const labels: Record<string, string> = {
      critical: 'Critical risk',
      high: 'High risk',
      medium: 'Medium risk',
      low: 'Low risk',
      compliant: 'No issues found',
      unknown: 'Unknown',
    };
    return labels[risk] ?? risk;
  }

  isDanger(sev: Severity | string): boolean {
    return sev === 'critical' || sev === 'high';
  }

  isWarning(sev: Severity | string): boolean {
    return sev === 'medium';
  }

  isInfo(sev: Severity | string): boolean {
    return sev === 'low' || sev === 'info';
  }

  statusLabel(status: RegulationVerdict['status']): string {
    const labels: Record<string, string> = {
      violation_likely: 'Violation likely',
      risk_identified: 'Risk identified',
      attention: 'Needs attention',
      compliant: 'Compliant',
      not_applicable: 'Not applicable',
    };
    return labels[status] ?? status;
  }

  statusIsBad(status: RegulationVerdict['status']): boolean {
    return status === 'violation_likely' || status === 'risk_identified';
  }

  statusIsWarn(status: RegulationVerdict['status']): boolean {
    return status === 'attention';
  }

  statusIsOk(status: RegulationVerdict['status']): boolean {
    return status === 'compliant' || status === 'not_applicable';
  }

  sortedFindings(verdict: RegulationVerdict): Finding[] {
    const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    return [...verdict.findings].sort(
      (a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9),
    );
  }

  totalFindings(report: AnalysisReport): number {
    return report.verdicts.reduce((n, v) => n + v.findings.length, 0);
  }
}
