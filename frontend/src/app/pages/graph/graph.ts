import { Component, computed, inject, signal } from '@angular/core';
import { EUI_CARD } from '@eui/components/eui-card';
import { EUI_CHIP } from '@eui/components/eui-chip';
import { ApiService } from '../../core/api.service';
import { GraphEdge, GraphFull, GraphNode } from '../../core/models';

/** Validated categorical palette (same set as the risk palette, reassigned by entity). */
const REGULATION_COLORS: Record<string, string> = {
  AI_ACT: '#006fb4',
  GDPR: '#467a39',
  DSA: '#d97706',
  UCPD: '#da2131',
};
const CONCEPT_COLOR = '#8f2d56';

interface PlacedNode extends GraphNode {
  x: number;
  y: number;
  r: number;
  color: string;
}

interface PlacedEdge extends GraphEdge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

const W = 1000;
const H = 700;
const CX = W / 2;
const CY = H / 2;

@Component({
  selector: 'app-graph',
  imports: [...EUI_CARD, ...EUI_CHIP],
  templateUrl: './graph.html',
  styleUrl: './graph.scss',
})
export class GraphPage {
  private readonly api = inject(ApiService);

  protected readonly W = W;
  protected readonly H = H;
  protected readonly conceptColor = CONCEPT_COLOR;
  protected readonly regulationColors = REGULATION_COLORS;

  protected readonly nodes = signal<PlacedNode[]>([]);
  protected readonly edges = signal<PlacedEdge[]>([]);
  protected readonly selectedId = signal<string | null>(null);
  protected readonly hoverId = signal<string | null>(null);
  protected readonly query = signal('');

  private adjacency = new Map<string, Set<string>>();
  private byId = new Map<string, PlacedNode>();

  protected readonly selected = computed(() =>
    this.selectedId() ? this.byId.get(this.selectedId()!) ?? null : null,
  );

  protected readonly neighbours = computed(() => {
    const id = this.selectedId();
    if (!id) {
      return [];
    }
    return this.edges()
      .filter((e) => e.source === id || e.target === id)
      .map((e) => ({
        edge: e,
        other: this.byId.get(e.source === id ? e.target : e.source)!,
        direction: e.source === id ? 'out' : 'in',
      }));
  });

  /** Nodes matching the search box (empty query -> none highlighted). */
  protected readonly matches = computed(() => {
    const q = this.query().trim().toLowerCase();
    if (q.length < 2) {
      return new Set<string>();
    }
    return new Set(
      this.nodes()
        .filter((n) =>
          `${n.title} ${n.ref} ${n.text}`.toLowerCase().includes(q))
        .map((n) => n.id),
    );
  });

  constructor() {
    this.api.graphFull().subscribe((g) => this.layout(g));
  }

  private layout(g: GraphFull): void {
    const regulations = g.nodes.filter((n) => n.type === 'regulation');
    const concepts = g.nodes.filter((n) => n.type === 'concept');
    const placed: PlacedNode[] = [];

    // Regulations: hubs on a mid-radius circle, one sector each.
    const sectorAngle = (2 * Math.PI) / regulations.length;
    const regAngle = new Map<string, number>();
    regulations.forEach((reg, i) => {
      const angle = -Math.PI / 2 + i * sectorAngle;
      regAngle.set(reg.regulation!, angle);
      placed.push(this.place(reg, CX + 190 * Math.cos(angle), CY + 190 * Math.sin(angle), 15));
    });

    // Provisions: arcs on the outer ring within their regulation's sector.
    for (const reg of regulations) {
      const provisions = g.nodes.filter(
        (n) => n.type === 'provision' && n.regulation === reg.regulation);
      const center = regAngle.get(reg.regulation!)!;
      const span = sectorAngle * 0.82;
      provisions.forEach((p, i) => {
        const t = provisions.length === 1 ? 0.5 : i / (provisions.length - 1);
        const angle = center - span / 2 + t * span;
        // stagger radius slightly so long sectors don't collide labels
        const radius = 295 + (i % 2) * 26;
        placed.push(this.place(p, CX + radius * Math.cos(angle), CY + radius * Math.sin(angle), 7));
      });
    }

    // Concepts: inner ring.
    concepts.forEach((c, i) => {
      const angle = -Math.PI / 2 + (i / concepts.length) * 2 * Math.PI;
      const radius = 92 + (i % 2) * 22;
      placed.push(this.place(c, CX + radius * Math.cos(angle), CY + radius * Math.sin(angle), 8));
    });

    this.byId = new Map(placed.map((n) => [n.id, n]));
    this.adjacency = new Map();
    const placedEdges: PlacedEdge[] = [];
    for (const e of g.edges) {
      const s = this.byId.get(e.source);
      const t = this.byId.get(e.target);
      if (!s || !t) {
        continue;
      }
      placedEdges.push({ ...e, x1: s.x, y1: s.y, x2: t.x, y2: t.y });
      if (!this.adjacency.has(e.source)) this.adjacency.set(e.source, new Set());
      if (!this.adjacency.has(e.target)) this.adjacency.set(e.target, new Set());
      this.adjacency.get(e.source)!.add(e.target);
      this.adjacency.get(e.target)!.add(e.source);
    }
    this.nodes.set(placed);
    this.edges.set(placedEdges);
  }

  private place(n: GraphNode, x: number, y: number, r: number): PlacedNode {
    const color = n.type === 'concept' ? CONCEPT_COLOR : REGULATION_COLORS[n.regulation ?? ''] ?? '#5b6873';
    return { ...n, x, y, r, color };
  }

  protected nodeState(id: string): 'normal' | 'active' | 'dimmed' {
    const focus = this.hoverId() ?? this.selectedId();
    const matches = this.matches();
    if (matches.size > 0) {
      return matches.has(id) ? 'active' : 'dimmed';
    }
    if (!focus) {
      return 'normal';
    }
    if (id === focus || this.adjacency.get(focus)?.has(id)) {
      return 'active';
    }
    return 'dimmed';
  }

  protected edgeState(e: PlacedEdge): 'normal' | 'active' | 'dimmed' {
    const focus = this.hoverId() ?? this.selectedId();
    if (this.matches().size > 0) {
      return 'dimmed';
    }
    if (!focus) {
      return 'normal';
    }
    return e.source === focus || e.target === focus ? 'active' : 'dimmed';
  }

  protected select(id: string): void {
    this.selectedId.set(this.selectedId() === id ? null : id);
  }

  protected shortLabel(n: PlacedNode): string {
    if (n.type === 'regulation') {
      return n.regulation === 'AI_ACT' ? 'AI Act'
        : n.regulation === 'UCPD' ? 'UCPD'
        : n.regulation ?? '';
    }
    const ref = n.ref ?? '';
    const art = ref.match(/Arts?\.\s*([\d\-a-z()]+)/i);
    const annex = ref.match(/Annex I, point (\w+)/i);
    if (annex) return `I.${annex[1]}`;
    if (art) return `${art[1]}`;
    return (n.title ?? '').slice(0, 12);
  }

  protected labelAnchor(n: PlacedNode): string {
    if (n.type === 'concept') return 'middle';
    return n.x >= CX ? 'start' : 'end';
  }

  protected labelDx(n: PlacedNode): number {
    if (n.type === 'concept') return 0;
    return n.x >= CX ? n.r + 4 : -(n.r + 4);
  }

  protected edgeDash(type: string): string | null {
    if (type === 'REFERENCES') return '5 4';
    if (type === 'RELATED_TO') return '2 4';
    return null;
  }
}
