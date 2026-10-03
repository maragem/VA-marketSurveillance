Configuration: E — single-call chat UI (GPT@EC) · model: gpt-5.4 · campaigns scored: 15 · runs/campaign: up to 2 · manual evaluation · worksheet: Run sheet

# Benchmark scorecard — engine: chat-ui (gpt-5.4)

- Cases run: **15** (2 compliant controls)
- Gold-provision recall: **0.615**
- Missed triage routings: **0**
- Unexpected actionable findings (review these): **27**
- False positives on compliant controls: **0/2**
- Risk calibration passed: **12/15**
- Invalid citations surviving to reports (would be removed by validation): **0**

| case | tier | risk (min) | ok | matched | missed | unexpected | routing missed | invalid | s |
|---|---|---|---|---|---|---|---|---|---|
| t1-countdown-timer | 1 | critical (high) | ✅ | ucpd-annex1-7 | — | — | — | 0 | — |
| t1-purchased-list-lookalike | 1 | high (high) | ✅ | gdpr-art21, gdpr-art6-1 | — | — | — | 0 | — |
| t1-voice-clone-radio | 1 | high (critical) | ❌ | aia-art50-4, ucpd-art6 | ucpd-annex1-23c | — | — | 0 | — |
| t1-guaranteed-loan-pressure | 1 | high (critical) | ❌ | ucpd-art6, ucpd-art8-9 | — | dsa-art25, dsa-art26-1, gdpr-art13 | — | 0 | — |
| t1-official-lookalike | 1 | critical (critical) | ✅ | ucpd-art6, ucpd-art7 | — | dsa-art25, dsa-art26-1 | — | 0 | — |
| t2-preselected-addons | 2 | high (high) | ✅ | ucpd-art7 | — | dsa-art25 | — | 0 | — |
| t2-gifted-influencer-vague | 2 | high (high) | ✅ | — | — | dsa-art26-1, ucpd-art5 | — | 0 | — |
| t2-drip-pricing-fees | 2 | high (high) | ❌ | ucpd-art7 | ucpd-art6 | dsa-art26-1, ucpd-annex1-11, ucpd-art5 | — | 0 | — |
| t2-retargeting-pressure | 2 | high (medium) | ✅ | gdpr-art21 | — | dsa-art26-1, gdpr-art5-1a, gdpr-art7, ucpd-annex1-26 | — | 0 | — |
| t2-personalised-price-hidden | 2 | high (high) | ✅ | gdpr-art13, gdpr-art5-1a, ucpd-art7 | — | dsa-art25, dsa-art26-1, gdpr-art12, gdpr-art4-11, gdpr-art7 | — | 0 | — |
| t3-compliant-green-certified | 3 | low (low) | ✅ | — | — | — | — | 0 | — |
| t3-compliant-urgency-deadline | 3 | compliant (low) | ✅ | — | — | — | — | 0 | — |
| t3-minors-adjacent-audience | 3 | medium (medium) | ❌ | — | ucpd-art5 | dsa-art26-1, gdpr-art21, gdpr-art5-1a, gdpr-art6-1 | — | 0 | — |
| t3-was-price-anchor | 3 | high (medium) | ✅ | ucpd-art6 | — | ucpd-art5 | — | 0 | — |
| t3-emotion-optimized-ads | 3 | high (critical) | ❌ | — | aia-art5-1a, aia-art5-1b, dsa-art25, dsa-art26-3, gdpr-art5-1a, gdpr-art6-1, ucpd-art8-9 | ucpd-art5, ucpd-art6 | — | 0 | — |

## Stability (mean pairwise Jaccard of finding sets across runs)

- t1-countdown-timer: 0.556
- t1-guaranteed-loan-pressure: 1.0
- t1-official-lookalike: 0.625
- t1-purchased-list-lookalike: 0.8
- t1-voice-clone-radio: 1.0
- t2-drip-pricing-fees: 0.286
- t2-gifted-influencer-vague: 0.6
- t2-personalised-price-hidden: 0.615
- t2-preselected-addons: 1.0
- t2-retargeting-pressure: 0.9
- t3-compliant-green-certified: 0.0
- t3-compliant-urgency-deadline: 1.0
- t3-emotion-optimized-ads: 0.071
- t3-minors-adjacent-audience: 0.75
- t3-was-price-anchor: 0.5
