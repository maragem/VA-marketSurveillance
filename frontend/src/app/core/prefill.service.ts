import { Injectable, signal } from '@angular/core';
import { CampaignSubmission } from './models';

/** Hands a pre-assembled campaign (e.g. from YouTube surveillance) to the analyze form. */
@Injectable({ providedIn: 'root' })
export class PrefillService {
  private readonly pending = signal<CampaignSubmission | null>(null);

  set(campaign: CampaignSubmission): void {
    this.pending.set(campaign);
  }

  /** Returns the pending prefill once, then clears it. */
  take(): CampaignSubmission | null {
    const value = this.pending();
    this.pending.set(null);
    return value;
  }
}
