import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService } from './core/api.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly api = inject(ApiService);
  protected readonly llmConfigured = signal<boolean | null>(null);
  protected readonly model = signal<string | null>(null);
  protected readonly year = new Date().getFullYear();

  constructor() {
    this.api.health().subscribe({
      next: (h) => {
        this.llmConfigured.set(h.llm_configured);
        this.model.set(h.model);
      },
      error: () => this.llmConfigured.set(false),
    });
  }
}
