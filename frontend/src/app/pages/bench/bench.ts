import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { EUI_ALERT } from '@eui/components/eui-alert';
import { EUI_BADGE } from '@eui/components/eui-badge';
import { EuiButtonComponent } from '@eui/components/eui-button';
import { EUI_CARD } from '@eui/components/eui-card';
import { ApiService } from '../../core/api.service';
import {
  AnalysisReport,
  BenchCase,
  BenchRunOutcome,
  BenchUnexpectedFinding,
  GraphNode,
  Regulation,
} from '../../core/models';

const RISK_ORDER: Record<string, number> = { compliant: 0, low: 1, medium: 2, high: 3, critical: 4, unknown: -1 };
const ACTIONABLE = ['critical', 'high', 'medium'];

/** Editable working copy of a case: list fields flattened to comma strings. */
interface Draft {
  id: string;
  tier: 1 | 2 | 3;
  source: string;
  title: string;
  text: string;
  channels: string;
  target_audience: string;
  markets: string;
  uses_ai_generation: boolean;
  uses_personalisation: boolean;
  compliant: boolean;
  relevant: Regulation[];
  provisions: string[];
  acceptable_extra: string[];
  min_risk: string;
  isNew: boolean;
}

const REGULATIONS: Regulation[] = ['AI_ACT', 'GDPR', 'DSA', 'UCPD'];
const RISKS = ['critical', 'high', 'medium', 'low', 'compliant'];

@Component({
  selector: 'app-bench',
  imports: [FormsModule, EuiButtonComponent, ...EUI_CARD, ...EUI_BADGE, ...EUI_ALERT],
  templateUrl: './bench.html',
  styleUrl: './bench.scss',
})
export class BenchPage {
  private readonly api = inject(ApiService);

  protected readonly regulations = REGULATIONS;
  protected readonly risks = RISKS;

  protected readonly cases = signal<BenchCase[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly expandedId = signal<string | null>(null);
  protected readonly saving = signal(false);
  protected readonly saveErrors = signal<string[]>([]);
  protected readonly savedTick = signal<string | null>(null);
  protected readonly provisionNodes = signal<GraphNode[]>([]);

  protected readonly running = signal(false);
  protected readonly runStatus = signal<string | null>(null);
  protected readonly runError = signal<string | null>(null);
  protected readonly outcome = signal<BenchRunOutcome | null>(null);
  protected readonly storedRuns = signal<Record<string, BenchRunOutcome>>({});
  protected readonly whyOpen = signal<string | null>(null);
  protected readonly adjudicatingId = signal<string | null>(null);
  protected readonly adjError = signal<string | null>(null);

  protected draft: Draft | null = null;
  private lastReport: AnalysisReport | null = null;
  private runAbort: AbortController | null = null;

  /** Provisions grouped per regulation, for the add-provision selects. */
  protected readonly provisionsByRegulation = computed(() => {
    const groups = new Map<string, GraphNode[]>();
    for (const reg of REGULATIONS) {
      groups.set(reg, this.provisionNodes().filter((n) => n.regulation === reg));
    }
    return groups;
  });

  constructor() {
    this.api.benchCases().subscribe({
      next: (r) => {
        this.cases.set(r.cases);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load the benchmark cases.');
        this.loading.set(false);
      },
    });
    this.api.graphFull().subscribe({
      next: (g) => this.provisionNodes.set(g.nodes.filter((n) => n.type === 'provision')),
    });
    this.api.benchRuns().subscribe({
      next: (runs) => {
        this.storedRuns.set(runs);
        // The user may have expanded a case before the stored runs arrived —
        // restore its outcome now.
        const expanded = this.expandedId();
        if (expanded && !this.outcome() && runs[expanded]) {
          this.outcome.set(runs[expanded]);
        }
      },
    });
  }

  protected runDate(outcome: BenchRunOutcome): string {
    return outcome.recorded_at ? `${outcome.recorded_at.slice(0, 16).replace('T', ' ')} UTC` : '';
  }

  protected provisionLabel(id: string): string {
    const node = this.provisionNodes().find((n) => n.id === id);
    return node ? `${node.ref} — ${node.title}` : id;
  }

  protected tierLabel(tier: number): string {
    return ({ 1: 'enforcement-inspired', 2: 'dataset-adapted', 3: 'synthetic' } as Record<number, string>)[tier] ?? `${tier}`;
  }

  protected toggle(benchCase: BenchCase): void {
    this.resetRun();
    if (this.expandedId() === benchCase.id) {
      this.expandedId.set(null);
      this.draft = null;
      return;
    }
    this.expandedId.set(benchCase.id);
    this.saveErrors.set([]);
    this.draft = this.toDraft(benchCase, false);
    // Restore the stored last-run comparison, if any (accept buttons still
    // work on it; a fresh Run recomputes against the live engine).
    const stored = this.storedRuns()[benchCase.id];
    if (stored) {
      this.outcome.set(stored);
    }
  }

  private resetRun(): void {
    this.runAbort?.abort();
    this.runAbort = null;
    this.running.set(false);
    this.runStatus.set(null);
    this.runError.set(null);
    this.outcome.set(null);
    this.lastReport = null;
    this.whyOpen.set(null);
    this.adjudicatingId.set(null);
    this.adjError.set(null);
  }

  protected toggleWhy(id: string): void {
    this.adjError.set(null);
    this.whyOpen.set(this.whyOpen() === id ? null : id);
  }

  protected adjVerdictLabel(verdict: string): string {
    return ({
      must_find: 'correct citation — should be a must-find',
      acceptable_extra: 'defensible — acceptable extra',
      reject: 'likely engine error — do not accept',
    } as Record<string, string>)[verdict] ?? verdict;
  }

  /** Ask the model for an adversarial second opinion on a disputed citation. */
  protected adjudicate(finding: BenchUnexpectedFinding): void {
    if (!this.draft || this.adjudicatingId()) return;
    const campaign = this.fromDraft(this.draft).campaign;
    this.adjudicatingId.set(finding.id);
    this.adjError.set(null);
    this.api.adjudicateFinding(campaign, {
      provision_id: finding.id,
      severity: finding.severity,
      rationale: finding.rationale,
      evidence_quote: finding.evidence_quote,
    }).subscribe({
      next: (adjudication) => {
        const o = this.outcome();
        if (o) {
          const updated = {
            ...o,
            unexpected: o.unexpected.map((u) => (u.id === finding.id ? { ...u, adjudication } : u)),
          };
          this.outcome.set(updated);
          this.persistRun(updated);
        }
        this.adjudicatingId.set(null);
      },
      error: (err) => {
        this.adjError.set(err?.error?.detail ?? 'Could not get a second opinion.');
        this.adjudicatingId.set(null);
      },
    });
  }

  protected applyAdjudication(finding: BenchUnexpectedFinding): void {
    const verdict = finding.adjudication?.verdict;
    if (verdict === 'must_find') {
      this.acceptUnexpected(finding.id, 'provisions');
    } else if (verdict === 'acceptable_extra') {
      this.acceptUnexpected(finding.id, 'acceptable_extra');
    }
  }

  private toDraft(c: BenchCase, isNew: boolean): Draft {
    return {
      id: c.id,
      tier: c.tier,
      source: c.source,
      title: c.campaign.title,
      text: c.campaign.text,
      channels: (c.campaign.channels ?? []).join(', '),
      target_audience: c.campaign.target_audience ?? '',
      markets: (c.campaign.markets ?? []).join(', '),
      uses_ai_generation: !!c.campaign.uses_ai_generation,
      uses_personalisation: !!c.campaign.uses_personalisation,
      compliant: c.gold.compliant,
      relevant: [...c.gold.relevant],
      provisions: [...c.gold.provisions],
      acceptable_extra: [...c.gold.acceptable_extra],
      min_risk: c.gold.min_risk,
      isNew,
    };
  }

  private fromDraft(d: Draft): BenchCase {
    const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);
    return {
      id: d.id.trim(),
      tier: d.tier,
      source: d.source.trim(),
      campaign: {
        title: d.title.trim(),
        text: d.text.trim(),
        channels: split(d.channels),
        target_audience: d.target_audience.trim() || null,
        markets: split(d.markets),
        uses_ai_generation: d.uses_ai_generation,
        uses_personalisation: d.uses_personalisation,
      },
      gold: {
        compliant: d.compliant,
        relevant: [...d.relevant],
        provisions: d.compliant ? [] : [...d.provisions],
        acceptable_extra: [...d.acceptable_extra],
        min_risk: d.min_risk as BenchCase['gold']['min_risk'],
      },
    };
  }

  protected relevantHas(reg: Regulation): boolean {
    return this.draft?.relevant.includes(reg) ?? false;
  }

  protected toggleRelevant(reg: Regulation): void {
    if (!this.draft) return;
    this.draft.relevant = this.relevantHas(reg)
      ? this.draft.relevant.filter((r) => r !== reg)
      : [...this.draft.relevant, reg];
  }

  protected addProvision(list: 'provisions' | 'acceptable_extra', event: Event): void {
    const select = event.target as HTMLSelectElement;
    const id = select.value;
    select.value = '';
    if (!this.draft || !id) return;
    if (!this.draft[list].includes(id)) {
      this.draft[list] = [...this.draft[list], id];
    }
    const other: 'provisions' | 'acceptable_extra' = list === 'provisions' ? 'acceptable_extra' : 'provisions';
    this.draft[other] = this.draft[other].filter((p) => p !== id);
  }

  protected removeProvision(list: 'provisions' | 'acceptable_extra', id: string): void {
    if (!this.draft) return;
    this.draft[list] = this.draft[list].filter((p) => p !== id);
  }

  protected moveProvision(from: 'provisions' | 'acceptable_extra', id: string): void {
    if (!this.draft) return;
    const to: 'provisions' | 'acceptable_extra' = from === 'provisions' ? 'acceptable_extra' : 'provisions';
    this.draft[from] = this.draft[from].filter((p) => p !== id);
    if (!this.draft[to].includes(id)) {
      this.draft[to] = [...this.draft[to], id];
    }
  }

  protected addCase(): void {
    this.resetRun();
    const existing = new Set(this.cases().map((c) => c.id));
    let n = 1;
    while (existing.has(`t3-new-case-${n}`)) n++;
    const blank: BenchCase = {
      id: `t3-new-case-${n}`,
      tier: 3,
      source: 'Describe where this case comes from / why it exists',
      campaign: {
        title: 'New case title',
        text: 'Describe the campaign: claims, mechanics, targeting, channels…',
        channels: [],
        target_audience: null,
        markets: ['EU'],
        uses_ai_generation: false,
        uses_personalisation: false,
      },
      gold: { compliant: false, relevant: [], provisions: [], acceptable_extra: [], min_risk: 'medium' },
    };
    this.cases.update((cs) => [blank, ...cs]);
    this.expandedId.set(blank.id);
    this.saveErrors.set([]);
    this.draft = this.toDraft(blank, true);
  }

  protected cancelEdit(benchCase: BenchCase): void {
    this.resetRun();
    if (this.draft?.isNew) {
      this.cases.update((cs) => cs.filter((c) => c.id !== benchCase.id));
    }
    this.expandedId.set(null);
    this.draft = null;
    this.saveErrors.set([]);
  }

  /** Run the case's campaign through the engine (not persisted) and compare
   *  the outcome against the gold labels currently on screen. */
  protected async runCase(): Promise<void> {
    if (!this.draft || this.running()) return;
    const campaign = this.fromDraft(this.draft).campaign;
    this.resetRun();
    this.running.set(true);
    this.runStatus.set('Submitting campaign…');
    this.runAbort = new AbortController();
    try {
      await this.api.analyzeStream(
        campaign,
        (event) => {
          const e = event as { type: string; message?: string; regulation?: string; report?: AnalysisReport };
          if (e.type === 'stage' && e.message) {
            this.runStatus.set(e.message);
          } else if (e.type === 'agent_completed' && e.regulation) {
            this.runStatus.set(`${e.regulation} specialist finished…`);
          } else if (e.type === 'report' && e.report) {
            this.lastReport = e.report;
            const outcome = this.compare(e.report);
            this.outcome.set(outcome);
            this.persistRun(outcome);
          } else if (e.type === 'error') {
            this.runError.set(e.message ?? 'Analysis failed.');
          }
        },
        null,
        this.runAbort.signal,
        false,
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        this.runError.set(err instanceof Error ? err.message : 'Analysis failed.');
      }
    } finally {
      this.running.set(false);
      this.runStatus.set(null);
      this.runAbort = null;
    }
  }

  /** Store the outcome server-side so the test result survives page reloads. */
  private persistRun(outcome: BenchRunOutcome): void {
    const caseId = this.expandedId();
    if (!caseId || this.draft?.isNew) {
      return;
    }
    this.api.saveBenchRun(caseId, outcome).subscribe({
      next: (stored) => {
        this.storedRuns.update((runs) => ({ ...runs, [caseId]: stored }));
        this.outcome.set(stored);
      },
    });
  }

  private compare(report: AnalysisReport): BenchRunOutcome {
    const d = this.draft!;
    const goldRelevant = new Set<string>(d.relevant);
    const goldProvisions = new Set(d.compliant ? [] : d.provisions);
    const allowed = new Set([...goldProvisions, ...d.acceptable_extra]);

    const routed = report.triage?.regulations_to_check ?? [];
    const all = report.verdicts.flatMap((v) => v.findings);
    const foundAny = new Set(all.map((f) => f.provision_id));
    const actionable = all.filter((f) => ACTIONABLE.includes(f.severity));

    const matched = [...goldProvisions].filter((p) => foundAny.has(p));
    const missed = [...goldProvisions].filter((p) => !foundAny.has(p));
    const seen = new Set<string>();
    const unexpected: BenchUnexpectedFinding[] = actionable
      .filter((f) => !allowed.has(f.provision_id) && !seen.has(f.provision_id) && seen.add(f.provision_id) !== undefined)
      .map((f) => ({
        id: f.provision_id,
        severity: f.severity,
        rationale: f.rationale,
        evidence_quote: f.evidence_quote,
      }));

    const riskRank = RISK_ORDER[report.overall_risk] ?? -1;
    const falsePositive = d.compliant && (actionable.length > 0 || riskRank >= RISK_ORDER['medium']);
    const riskOk = d.compliant ? !falsePositive : riskRank >= (RISK_ORDER[d.min_risk] ?? 2);
    const routingMissed = [...goldRelevant].filter((r) => !routed.includes(r as Regulation));

    return {
      engine: report.engine,
      overallRisk: report.overall_risk,
      riskOk,
      compliantControl: d.compliant,
      falsePositive,
      routed,
      routingMissed,
      routingExtra: routed.filter((r) => !goldRelevant.has(r)),
      matched,
      missed,
      unexpected,
      pass: riskOk && missed.length === 0 && routingMissed.length === 0 && !falsePositive && unexpected.length === 0,
    };
  }

  /** Accept an unexpected finding into the gold labels and re-compare. */
  protected acceptUnexpected(id: string, list: 'provisions' | 'acceptable_extra'): void {
    if (!this.draft) return;
    if (list === 'provisions') {
      const node = this.provisionNodes().find((n) => n.id === id);
      if (node?.regulation && !this.draft.relevant.includes(node.regulation as Regulation)) {
        this.draft.relevant = [...this.draft.relevant, node.regulation as Regulation];
      }
    }
    if (!this.draft[list].includes(id)) {
      this.draft[list] = [...this.draft[list], id];
    }
    if (this.lastReport) {
      const updated = this.compare(this.lastReport);
      this.outcome.set(updated);
      this.persistRun(updated);
      return;
    }
    // Stored outcome (no live report this session): update it in place.
    const o = this.outcome();
    if (o) {
      const unexpected = o.unexpected.filter((u) => u.id !== id);
      const matched = list === 'provisions' && !o.matched.includes(id) ? [...o.matched, id] : o.matched;
      const pass = o.riskOk && o.missed.length === 0 && o.routingMissed.length === 0
        && !o.falsePositive && unexpected.length === 0;
      const updated = { ...o, unexpected, matched, pass };
      this.outcome.set(updated);
      this.persistRun(updated);
    }
  }

  protected save(original: BenchCase): void {
    if (!this.draft || this.saving()) return;
    const updated = this.fromDraft(this.draft);
    const wasNew = this.draft.isNew;
    if (!wasNew && updated.id !== original.id) {
      this.saveErrors.set(['Case ids are stable — add a new case instead of renaming.']);
      return;
    }
    this.saving.set(true);
    this.saveErrors.set([]);
    const request = wasNew ? this.api.createBenchCase(updated) : this.api.updateBenchCase(updated);
    request.subscribe({
      next: () => {
        this.cases.update((cs) => cs.map((c) => (c.id === original.id ? updated : c)));
        this.saving.set(false);
        this.expandedId.set(null);
        this.draft = null;
        this.savedTick.set(updated.id);
        setTimeout(() => this.savedTick.set(null), 2500);
      },
      error: (err) => {
        const detail = err?.error?.detail;
        this.saveErrors.set(Array.isArray(detail) ? detail : [detail ?? 'Could not save the case.']);
        this.saving.set(false);
      },
    });
  }

  protected remove(benchCase: BenchCase): void {
    if (!confirm(`Delete case "${benchCase.id}" from the benchmark?`)) return;
    this.api.deleteBenchCase(benchCase.id).subscribe({
      next: () => {
        this.cases.update((cs) => cs.filter((c) => c.id !== benchCase.id));
        this.storedRuns.update((runs) => {
          const { [benchCase.id]: _removed, ...rest } = runs;
          return rest;
        });
        if (this.expandedId() === benchCase.id) {
          this.expandedId.set(null);
          this.draft = null;
        }
      },
      error: (err) => this.error.set(err?.error?.detail ?? 'Could not delete the case.'),
    });
  }
}
