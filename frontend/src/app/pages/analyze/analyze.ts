import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { EUI_ALERT } from '@eui/components/eui-alert';
import { EUI_BADGE } from '@eui/components/eui-badge';
import { EuiButtonComponent } from '@eui/components/eui-button';
import { EUI_CARD } from '@eui/components/eui-card';
import { ApiService } from '../../core/api.service';
import { EXAMPLE_CAMPAIGNS, ExampleCampaign } from '../../core/examples';
import {
  AnalysisReport,
  CampaignSubmission,
  REGULATION_LABELS,
  Regulation,
  StreamEvent,
} from '../../core/models';
import { ReportView } from '../../shared/report-view';

interface ProgressLine {
  kind: 'stage' | 'agent' | 'tool' | 'error';
  regulation?: Regulation;
  text: string;
}

type AgentState = 'pending' | 'running' | 'done';

@Component({
  selector: 'app-analyze',
  imports: [FormsModule, ReportView, EuiButtonComponent, ...EUI_CARD, ...EUI_ALERT, ...EUI_BADGE],
  templateUrl: './analyze.html',
  styleUrl: './analyze.scss',
})
export class AnalyzePage {
  private readonly api = inject(ApiService);

  protected readonly regulationLabels = REGULATION_LABELS;
  protected readonly examples = EXAMPLE_CAMPAIGNS;

  // form model
  protected title = '';
  protected text = '';
  protected channels = '';
  protected audience = '';
  protected markets = '';
  protected usesAi = false;
  protected usesPersonalisation = false;

  protected readonly phase = signal<'form' | 'running' | 'done' | 'failed'>('form');
  protected readonly progress = signal<ProgressLine[]>([]);
  protected readonly agentStates = signal<Partial<Record<Regulation, AgentState>>>({});
  protected readonly report = signal<AnalysisReport | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  protected agentEntries(): { regulation: Regulation; state: AgentState }[] {
    return Object.entries(this.agentStates()).map(([regulation, state]) => ({
      regulation: regulation as Regulation,
      state: state as AgentState,
    }));
  }

  protected loadExample(example: ExampleCampaign): void {
    const c = example.campaign;
    this.title = c.title;
    this.text = c.text;
    this.channels = c.channels.join(', ');
    this.audience = c.target_audience ?? '';
    this.markets = c.markets.join(', ');
    this.usesAi = !!c.uses_ai_generation;
    this.usesPersonalisation = !!c.uses_personalisation;
    this.errorMessage.set(null);
  }

  protected canSubmit(): boolean {
    return this.title.trim().length > 0 && this.text.trim().length >= 20;
  }

  protected async submit(): Promise<void> {
    if (!this.canSubmit() || this.phase() === 'running') {
      return;
    }
    const campaign: CampaignSubmission = {
      title: this.title.trim(),
      text: this.text.trim(),
      channels: this.splitList(this.channels),
      target_audience: this.audience.trim() || null,
      markets: this.splitList(this.markets),
      uses_ai_generation: this.usesAi,
      uses_personalisation: this.usesPersonalisation,
    };
    this.phase.set('running');
    this.progress.set([]);
    this.agentStates.set({});
    this.report.set(null);
    this.errorMessage.set(null);
    try {
      await this.api.analyzeStream(campaign, (event) => this.onEvent(event));
      if (this.phase() === 'running') {
        this.phase.set(this.report() ? 'done' : 'failed');
      }
    } catch (err) {
      this.errorMessage.set(err instanceof Error ? err.message : 'Analysis failed.');
      this.phase.set('failed');
    }
  }

  protected reset(): void {
    this.phase.set('form');
    this.report.set(null);
    this.progress.set([]);
    this.agentStates.set({});
    this.errorMessage.set(null);
  }

  private splitList(value: string): string[] {
    return value.split(',').map((v) => v.trim()).filter(Boolean);
  }

  private pushProgress(line: ProgressLine): void {
    this.progress.update((lines) => [...lines, line].slice(-60));
  }

  private setAgent(reg: Regulation, state: AgentState): void {
    this.agentStates.update((s) => ({ ...s, [reg]: state }));
  }

  private onEvent(event: StreamEvent): void {
    switch (event.type) {
      case 'stage':
        this.pushProgress({ kind: 'stage', text: String(event['message'] ?? '') });
        break;
      case 'triage': {
        const triage = event['triage'] as { regulations_to_check?: Regulation[] } | undefined;
        for (const reg of triage?.regulations_to_check ?? []) {
          this.setAgent(reg, 'pending');
        }
        this.pushProgress({ kind: 'stage', text: 'Triage completed.' });
        break;
      }
      case 'agent_started':
        this.setAgent(event['regulation'] as Regulation, 'running');
        this.pushProgress({
          kind: 'agent',
          regulation: event['regulation'] as Regulation,
          text: `${this.regulationLabels[event['regulation'] as Regulation]} agent started.`,
        });
        break;
      case 'agent_tool_call': {
        const input = event['input'] as { query?: string; node_id?: string } | undefined;
        const detail = input?.query ?? input?.node_id ?? '';
        this.pushProgress({
          kind: 'tool',
          regulation: event['regulation'] as Regulation,
          text: `${event['regulation']} → ${event['tool']}(${detail})`,
        });
        break;
      }
      case 'agent_completed': {
        const reg = event['regulation'] as Regulation;
        this.setAgent(reg, 'done');
        const verdict = event['verdict'] as { findings?: unknown[]; status?: string } | undefined;
        this.pushProgress({
          kind: 'agent',
          regulation: reg,
          text: `${this.regulationLabels[reg]} agent finished: ${verdict?.status} (${verdict?.findings?.length ?? 0} findings).`,
        });
        break;
      }
      case 'report':
        this.report.set(event['report'] as unknown as AnalysisReport);
        this.phase.set('done');
        break;
      case 'error':
        this.errorMessage.set(String(event['message'] ?? 'Analysis failed.'));
        this.phase.set('failed');
        break;
    }
  }
}
