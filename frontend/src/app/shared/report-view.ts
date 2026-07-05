import { Component, input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { EUI_ALERT } from '@eui/components/eui-alert';
import { EUI_BADGE } from '@eui/components/eui-badge';
import { EUI_CARD } from '@eui/components/eui-card';
import { EUI_CHIP } from '@eui/components/eui-chip';
import {
  AnalysisReport,
  Finding,
  REGULATION_LABELS,
  Regulation,
  RegulationVerdict,
  Severity,
} from '../core/models';

@Component({
  selector: 'app-report-view',
  imports: [DatePipe, ...EUI_CARD, ...EUI_ALERT, ...EUI_BADGE, ...EUI_CHIP],
  templateUrl: './report-view.html',
  styleUrl: './report-view.scss',
})
export class ReportView {
  readonly report = input.required<AnalysisReport>();

  readonly regulationLabels = REGULATION_LABELS;

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
