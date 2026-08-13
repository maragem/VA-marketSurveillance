Configuration: C — Default on holdout (D baseline) · job C-holdout-20260813-083740 · model: eu.anthropic.claude-opus-4-8 · cases sha256: 54ff841181b4621b

# Benchmark scorecard — engine: agentic

- Cases run: **15** (2 compliant controls)
- Gold-provision recall: **1.0**
- Missed triage routings: **0**
- Unexpected actionable findings (review these): **44**
- False positives on compliant controls: **0/2**
- Risk calibration passed: **15/15**
- Invalid citations surviving to reports (would be removed by validation): **0**
- Mean latency per case: **58.6s**

| case | tier | risk (min) | ok | matched | missed | unexpected | routing missed | invalid | s |
|---|---|---|---|---|---|---|---|---|---|
| t1-countdown-timer | 1 | critical (high) | ✅ | ucpd-annex1-7 | — | ucpd-art8-9 | — | 0 | 46.5 |
| t1-purchased-list-lookalike | 1 | critical (high) | ✅ | gdpr-art21, gdpr-art6-1 | — | dsa-art26-3, ucpd-art8-9 | — | 0 | 73.3 |
| t1-voice-clone-radio | 1 | critical (critical) | ✅ | aia-art50-4, ucpd-annex1-23c, ucpd-art6 | — | aia-art5-1a, aia-art50-2, gdpr-art9 | — | 0 | 54.6 |
| t1-guaranteed-loan-pressure | 1 | critical (critical) | ✅ | ucpd-art6, ucpd-art8-9 | — | dsa-art25, dsa-art26-1, dsa-art26-3, gdpr-art13, gdpr-art9, ucpd-art5 | — | 0 | 64.3 |
| t1-official-lookalike | 1 | critical (critical) | ✅ | ucpd-art6, ucpd-art7 | — | aia-art5-1a, aia-art5-1b, aia-art50-2, aia-art50-4, dsa-art25, dsa-art26-1, gdpr-art12, gdpr-art6-1, ucpd-annex1-2, ucpd-annex1-7, ucpd-art5 | — | 0 | 72.3 |
| t2-preselected-addons | 2 | high (high) | ✅ | ucpd-art7 | — | ucpd-art5 | — | 0 | 57.9 |
| t2-gifted-influencer-vague | 2 | high (high) | ✅ | — | — | dsa-art26-1 | — | 0 | 60.8 |
| t2-drip-pricing-fees | 2 | high (high) | ✅ | ucpd-art6, ucpd-art7 | — | — | — | 0 | 49.5 |
| t2-retargeting-pressure | 2 | critical (medium) | ✅ | gdpr-art21 | — | dsa-art25, dsa-art26-1, gdpr-art4-11, gdpr-art5-1a, gdpr-art7, ucpd-annex1-26, ucpd-art5 | — | 0 | 62.7 |
| t2-personalised-price-hidden | 2 | high (high) | ✅ | gdpr-art13, gdpr-art5-1a, ucpd-art7 | — | gdpr-art4-11, gdpr-art4-4, ucpd-art5 | — | 0 | 64.6 |
| t3-compliant-green-certified | 3 | low (low) | ✅ | — | — | — | — | 0 | 47.3 |
| t3-compliant-urgency-deadline | 3 | low (low) | ✅ | — | — | — | — | 0 | 45.3 |
| t3-minors-adjacent-audience | 3 | high (medium) | ✅ | ucpd-art5 | — | dsa-art26-1, gdpr-art5-1a, gdpr-art6-1, gdpr-art8, ucpd-annex1-11 | — | 0 | 65.9 |
| t3-was-price-anchor | 3 | high (medium) | ✅ | ucpd-art6 | — | — | — | 0 | 41.3 |
| t3-emotion-optimized-ads | 3 | critical (critical) | ✅ | aia-art5-1a, aia-art5-1b, dsa-art25, dsa-art26-3, gdpr-art5-1a, gdpr-art6-1, ucpd-art8-9 | — | dsa-art27, dsa-art39, gdpr-art7, ucpd-art5 | — | 0 | 72.0 |

## Stability (mean pairwise Jaccard of finding sets across runs)

- t1-countdown-timer: 0.738
- t1-guaranteed-loan-pressure: 0.826
- t1-official-lookalike: 0.889
- t1-purchased-list-lookalike: 0.694
- t1-voice-clone-radio: 0.933
- t2-drip-pricing-fees: 0.56
- t2-gifted-influencer-vague: 0.581
- t2-personalised-price-hidden: 0.879
- t2-preselected-addons: 0.7
- t2-retargeting-pressure: 0.842
- t3-compliant-green-certified: 0.556
- t3-compliant-urgency-deadline: 0.778
- t3-emotion-optimized-ads: 0.806
- t3-minors-adjacent-audience: 0.944
- t3-was-price-anchor: 0.444
