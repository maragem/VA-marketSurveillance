Configuration: E — single-call chat UI (GPT@EC) · model: gpt-oss-120b · campaigns scored: 15 · runs/campaign: up to 2 · manual evaluation · worksheet: gpt-oss-120b

# Benchmark scorecard — engine: chat-ui (gpt-oss-120b)

- Cases run: **15** (2 compliant controls)
- Gold-provision recall: **0.538**
- Missed triage routings: **0**
- Unexpected actionable findings (review these): **31**
- False positives on compliant controls: **2/2**
- Risk calibration passed: **13/15**
- Invalid citations surviving to reports (would be removed by validation): **0**

| case | tier | risk (min) | ok | matched | missed | unexpected | routing missed | invalid | s |
|---|---|---|---|---|---|---|---|---|---|
| t1-countdown-timer | 1 | critical (high) | ✅ | ucpd-annex1-7 | — | dsa-art25, dsa-art26-1 | — | 0 | — |
| t1-purchased-list-lookalike | 1 | critical (high) | ✅ | gdpr-art21, gdpr-art6-1 | — | — | — | 0 | — |
| t1-voice-clone-radio | 1 | critical (critical) | ❌ | ucpd-art6 | aia-art50-4, ucpd-annex1-23c | aia-art5-1a, aia-art50-1, dsa-art26-1, gdpr-art4-11, ucpd-annex1-4 | — | 0 | — |
| t1-guaranteed-loan-pressure | 1 | critical (critical) | ❌ | ucpd-art6 | ucpd-art8-9 | aia-art5-1b, dsa-art25, dsa-art26-1, dsa-art27, gdpr-art13 | — | 0 | — |
| t1-official-lookalike | 1 | critical (critical) | ✅ | ucpd-art6, ucpd-art7 | — | aia-art5-1a, dsa-art26-1, ucpd-annex1-11, ucpd-annex1-20 | — | 0 | — |
| t2-preselected-addons | 2 | high (high) | ❌ | — | ucpd-art7 | dsa-art25 | — | 0 | — |
| t2-gifted-influencer-vague | 2 | critical (high) | ✅ | — | — | dsa-art26-1 | — | 0 | — |
| t2-drip-pricing-fees | 2 | high (high) | ✅ | ucpd-art6, ucpd-art7 | — | — | — | 0 | — |
| t2-retargeting-pressure | 2 | critical (medium) | ✅ | gdpr-art21 | — | dsa-art25, dsa-art26-1, ucpd-annex1-26 | — | 0 | — |
| t2-personalised-price-hidden | 2 | critical (high) | ❌ | gdpr-art13 | gdpr-art5-1a, ucpd-art7 | aia-art5-1a, dsa-art25 | — | 0 | — |
| t3-compliant-green-certified | 3 | high (low) | ❌ | — | — | dsa-art26-1 | — | 0 | — |
| t3-compliant-urgency-deadline | 3 | high (low) | ❌ | — | — | dsa-art26-1, gdpr-art13 | — | 0 | — |
| t3-minors-adjacent-audience | 3 | critical (medium) | ❌ | — | ucpd-art5 | dsa-art26-1, ucpd-annex1-11 | — | 0 | — |
| t3-was-price-anchor | 3 | high (medium) | ✅ | ucpd-art6 | — | dsa-art26-1 | — | 0 | — |
| t3-emotion-optimized-ads | 3 | critical (critical) | ❌ | aia-art5-1a, dsa-art25 | aia-art5-1b, dsa-art26-3, gdpr-art5-1a, gdpr-art6-1, ucpd-art8-9 | dsa-art27, gdpr-art12 | — | 0 | — |

## Stability (mean pairwise Jaccard of finding sets across runs)

- t1-countdown-timer: 1.0
- t1-guaranteed-loan-pressure: 0.545
- t1-official-lookalike: 0.556
- t1-purchased-list-lookalike: 0.667
- t1-voice-clone-radio: 0.4
- t2-drip-pricing-fees: 0.667
- t2-gifted-influencer-vague: 1.0
- t2-personalised-price-hidden: 0.667
- t2-preselected-addons: 0.333
- t2-retargeting-pressure: 0.375
- t3-compliant-green-certified: 1.0
- t3-compliant-urgency-deadline: 0.5
- t3-emotion-optimized-ads: 0.778
- t3-minors-adjacent-audience: 0.6
- t3-was-price-anchor: 0.5
