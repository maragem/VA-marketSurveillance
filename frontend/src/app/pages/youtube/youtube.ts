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
  protected directUrl = '';
  protected language = 'auto';

  protected readonly languages: { code: string; label: string }[] = [
    { code: 'auto', label: 'transcript: auto' },
    { code: 'bg', label: 'Bulgarian' }, { code: 'cs', label: 'Czech' },
    { code: 'da', label: 'Danish' }, { code: 'de', label: 'German' },
    { code: 'el', label: 'Greek' }, { code: 'en', label: 'English' },
    { code: 'es', label: 'Spanish' }, { code: 'et', label: 'Estonian' },
    { code: 'fi', label: 'Finnish' }, { code: 'fr', label: 'French' },
    { code: 'hr', label: 'Croatian' }, { code: 'hu', label: 'Hungarian' },
    { code: 'it', label: 'Italian' }, { code: 'lt', label: 'Lithuanian' },
    { code: 'lv', label: 'Latvian' }, { code: 'mt', label: 'Maltese' },
    { code: 'nl', label: 'Dutch' }, { code: 'pl', label: 'Polish' },
    { code: 'pt', label: 'Portuguese' }, { code: 'ro', label: 'Romanian' },
    { code: 'sk', label: 'Slovak' }, { code: 'sl', label: 'Slovenian' },
    { code: 'sv', label: 'Swedish' },
  ];

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
    this.analyseById(video.video_id, video.title, video.description);
  }

  /** Extract the video id from a pasted YouTube URL (or a bare 11-char id). */
  protected parseVideoId(input: string): string | null {
    const trimmed = input.trim();
    if (/^[A-Za-z0-9_-]{11}$/.test(trimmed)) {
      return trimmed;
    }
    const match = trimmed.match(
      /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/,
    );
    return match ? match[1] : null;
  }

  protected analyseUrl(): void {
    const videoId = this.parseVideoId(this.directUrl);
    if (!videoId) {
      this.error.set('Could not recognise a YouTube video URL. Supported: youtube.com/watch?v=…, youtu.be/…, shorts, embed.');
      return;
    }
    this.analyseById(videoId);
  }

  private analyseById(videoId: string, fallbackTitle = '', fallbackText = ''): void {
    if (this.fetchingId()) {
      return;
    }
    this.fetchingId.set(videoId);
    this.error.set(null);
    this.api.youtubeVideo(videoId, this.language).subscribe({
      next: (bundle) => {
        const sections = [
          bundle.description ? `Video description:\n${bundle.description}` : '',
          bundle.transcript ? `Transcript:\n${bundle.transcript}` : '',
        ].filter(Boolean);
        this.prefill.set({
          title: this.deriveTitle(bundle, fallbackTitle, videoId),
          text: sections.join('\n\n') || fallbackText,
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

  /** Human-readable report title even when the video metadata has no title:
   *  fall back to "<channel> — <content snippet>" rather than a bare video id. */
  private deriveTitle(
    bundle: { title: string; channel: string; description: string; transcript: string },
    fallbackTitle: string,
    videoId: string,
  ): string {
    if (bundle.title.trim()) {
      return bundle.title.trim();
    }
    if (fallbackTitle.trim()) {
      return fallbackTitle.trim();
    }
    const snippet = (bundle.description || bundle.transcript || '').replace(/\s+/g, ' ').trim();
    const cut = snippet.lastIndexOf(' ', 80);
    const clipped = snippet.length > 80 ? `${snippet.slice(0, cut > 40 ? cut : 80)}…` : snippet;
    const channel = bundle.channel.trim();
    if (channel && clipped) {
      return `${channel} — ${clipped}`;
    }
    return clipped || (channel ? `${channel} (YouTube video)` : `YouTube video ${videoId}`);
  }
}
