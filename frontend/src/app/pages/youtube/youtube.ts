import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { EUI_ALERT } from '@eui/components/eui-alert';
import { EuiButtonComponent } from '@eui/components/eui-button';
import { EUI_CARD } from '@eui/components/eui-card';
import { ApiService } from '../../core/api.service';
import { PrefillService } from '../../core/prefill.service';
import { YouTubeSearchResult } from '../../core/models';

@Component({
  selector: 'app-youtube',
  imports: [FormsModule, EuiButtonComponent, ...EUI_CARD, ...EUI_ALERT],
  templateUrl: './youtube.html',
  styleUrl: './youtube.scss',
})
export class YouTubePage {
  private readonly api = inject(ApiService);
  private readonly prefill = inject(PrefillService);
  private readonly router = inject(Router);

  protected query = '';
  protected uploadDate = '';
  protected sortBy = 'relevance';

  protected readonly configured = signal<boolean | null>(null);
  protected readonly searching = signal(false);
  protected readonly results = signal<YouTubeSearchResult[]>([]);
  protected readonly searched = signal(false);
  protected readonly fetchingId = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.api.health().subscribe({
      next: (h) => this.configured.set((h as { youtube_configured?: boolean }).youtube_configured ?? false),
      error: () => this.configured.set(false),
    });
  }

  protected search(): void {
    const q = this.query.trim();
    if (!q || this.searching()) {
      return;
    }
    this.searching.set(true);
    this.error.set(null);
    this.api.youtubeSearch(q, this.uploadDate || undefined, this.sortBy || undefined).subscribe({
      next: (results) => {
        this.results.set(results);
        this.searched.set(true);
        this.searching.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Search failed.');
        this.searching.set(false);
      },
    });
  }

  protected analyse(video: YouTubeSearchResult): void {
    if (this.fetchingId()) {
      return;
    }
    this.fetchingId.set(video.video_id);
    this.error.set(null);
    this.api.youtubeVideo(video.video_id).subscribe({
      next: (bundle) => {
        const sections = [
          bundle.description ? `Video description:\n${bundle.description}` : '',
          bundle.transcript ? `Transcript:\n${bundle.transcript}` : '',
        ].filter(Boolean);
        this.prefill.set({
          title: bundle.title || video.title,
          text: sections.join('\n\n') || video.description,
          channels: ['youtube'],
          target_audience: null,
          markets: [],
          uses_ai_generation: null,
          uses_personalisation: null,
          source_platform: 'YouTube',
          source_url: bundle.url,
        });
        this.fetchingId.set(null);
        this.router.navigate(['/analyze']);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Could not retrieve the video content.');
        this.fetchingId.set(null);
      },
    });
  }
}
