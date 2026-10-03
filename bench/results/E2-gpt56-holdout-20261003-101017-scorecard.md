Configuration: E — single-call chat UI (GPT@EC) · model: gpt-5.6 · campaigns scored: 15 · runs/campaign: up to 2 · manual evaluation · worksheet: Run sheet Evaluation -5.6

# Benchmark scorecard — engine: chat-ui (gpt-5.6)

- Cases run: **15** (2 compliant controls)
- Gold-provision recall: **0.692**
- Missed triage routings: **0**
- Unexpected actionable findings (review these): **4**
- False positives on compliant controls: **0/2**
- Risk calibration passed: **10/15**
- Invalid citations surviving to reports (would be removed by validation): **0**

| case | tier | risk (min) | ok | matched | missed | unexpected | routing missed | invalid | s |
|---|---|---|---|---|---|---|---|---|---|
| t1-countdown-timer | 1 | critical (high) | ✅ | ucpd-annex1-7 | — | — | — | 0 | — |
| t1-purchased-list-lookalike | 1 | high (high) | ✅ | gdpr-art21, gdpr-art6-1 | — | — | — | 0 | — |
| t1-voice-clone-radio | 1 | high (critical) | ❌ | aia-art50-4, ucpd-art6 | ucpd-annex1-23c | — | — | 0 | — |
| t1-guaranteed-loan-pressure | 1 | high (critical) | ❌ | ucpd-art6 | ucpd-art8-9 | — | — | 0 | — |
| t1-official-lookalike | 1 | high (critical) | ❌ | ucpd-art6, ucpd-art7 | — | dsa-art26-1 | — | 0 | — |
| t2-preselected-addons | 2 | medium (high) | ❌ | ucpd-art7 | — | — | — | 0 | — |
| t2-gifted-influencer-vague | 2 | critical (high) | ✅ | — | — | dsa-art26-1 | — | 0 | — |
| t2-drip-pricing-fees | 2 | high (high) | ✅ | ucpd-art6, ucpd-art7 | — | — | — | 0 | — |
| t2-retargeting-pressure | 2 | high (medium) | ✅ | gdpr-art21 | — | gdpr-art7 | — | 0 | — |
| t2-personalised-price-hidden | 2 | high (high) | ❌ | gdpr-art13, gdpr-art5-1a | ucpd-art7 | — | — | 0 | — |
| t3-compliant-green-certified | 3 | compliant (low) | ✅ | — | — | — | — | 0 | — |
| t3-compliant-urgency-deadline | 3 | compliant (low) | ✅ | — | — | — | — | 0 | — |
| t3-minors-adjacent-audience | 3 | medium (medium) | ❌ | — | ucpd-art5 | dsa-art26-1 | — | 0 | — |
| t3-was-price-anchor | 3 | high (medium) | ✅ | ucpd-art6 | — | — | — | 0 | — |
| t3-emotion-optimized-ads | 3 | high (critical) | ❌ | aia-art5-1a, dsa-art25, ucpd-art8-9 | aia-art5-1b, dsa-art26-3, gdpr-art5-1a, gdpr-art6-1 | — | — | 0 | — |

## Stability (mean pairwise Jaccard of finding sets across runs)

- t1-countdown-timer: 1.0
- t1-guaranteed-loan-pressure: 0.143
- t1-official-lookalike: 1.0
- t1-purchased-list-lookalike: 0.667
- t1-voice-clone-radio: 1.0
- t2-drip-pricing-fees: 1.0
- t2-gifted-influencer-vague: 1.0
- t2-personalised-price-hidden: 0.8
- t2-preselected-addons: 0.5
- t2-retargeting-pressure: 0.333
- t3-compliant-green-certified: 1.0
- t3-compliant-urgency-deadline: 1.0
- t3-emotion-optimized-ads: 0.625
- t3-minors-adjacent-audience: 0.0
- t3-was-price-anchor: 1.0
