import { CampaignSubmission } from './models';

export interface ExampleCampaign {
  label: string;
  description: string;
  campaign: CampaignSubmission;
}

/**
 * Fictional demo campaigns. The first one is deliberately packed with
 * practices that violate the AI Act, GDPR, DSA and UCPD so users can see the
 * full breadth of the analysis in one run.
 */
export const EXAMPLE_CAMPAIGNS: ExampleCampaign[] = [
  {
    label: 'High-risk demo: "GlowUp Miracle Tea"',
    description: 'Deliberately violates all four regulations — cure claims, minors, fake urgency, undisclosed AI, sensitive targeting.',
    campaign: {
      title: 'GlowUp Miracle Tea — Back-to-School Glow Blitz',
      text: [
        'Product: GlowUp Miracle Tea, a herbal drink. Key message: "Clinically proven to CURE acne,',
        'anxiety and sleep problems in 7 days — doctors hate this trick!" We have no clinical studies,',
        'but the claim converts extremely well.',
        '',
        'Audience & targeting: primary audience is teenagers 13-17 on TikTok and Instagram. We use',
        'platform ad tools to build audiences from inferred interests including "acne", "depression",',
        '"eating disorder recovery" and "anxiety", and our AI targeting engine detects when users are',
        'in a sad or anxious mood (late-night scrolling, sad-song playlists) to serve ads at their most',
        'vulnerable moments, because conversion doubles then.',
        '',
        'Creative: our virtual influencer "Mia Chen" (fully AI-generated, but presented as a real',
        '19-year-old student — we never mention she is synthetic) posts daily "honest diary" videos',
        'about how the tea cured her acne. We also run AI face-swap videos of a famous dermatologist',
        'appearing to endorse the product (she has no relationship with us). Creative copy tells kids:',
        '"Ask your mum to buy you the Glow Bundle before it\'s gone!"',
        '',
        'Mechanics: landing page shows a countdown timer ("Offer ends in 09:59") that resets on every',
        'visit, and a fake stock counter ("Only 3 boxes left!"). The "FREE starter pack" requires',
        'entering card details and silently converts into a €39.99/month subscription after 7 days;',
        'cancellation is only possible by phone on weekdays 9-11am. A pop-up tells every visitor',
        '"Congratulations, you WON a free year of GlowUp!" — clicking it just opens the subscription',
        'checkout.',
        '',
        'Engagement: an AI chatbot called "Nurse Sophie" chats with visitors as if she were a licensed',
        'human nutritionist and never discloses being a bot. She collects name, age, skin condition and',
        'mood diary entries, which we add to our ad-retargeting pool. The newsletter checkbox is',
        'pre-ticked and contest entry is only possible if marketing consent is given. We also purchased',
        '5,000 five-star reviews from a click farm and generate additional "verified customer" reviews',
        'with AI. Paid advertorials in school-newspaper websites are formatted as independent editorial',
        'articles with no ad label.',
      ].join('\n'),
      channels: ['tiktok', 'instagram', 'web', 'email'],
      target_audience: 'teenagers 13-17, plus users with inferred health interests (acne, anxiety)',
      markets: ['EU'],
      uses_ai_generation: true,
      uses_personalisation: true,
    },
  },
  {
    label: 'Medium-risk demo: "FitCoach AI"',
    description: 'Subtler issues — AI transparency gaps, aggressive retargeting, unclear trial terms.',
    campaign: {
      title: 'FitCoach AI — New Year Transformation',
      text: [
        'Product: FitCoach AI, a fitness-coaching app. Message: "Your personal AI coach builds the',
        'perfect plan for your body." Campaign runs on Instagram and YouTube targeting adults 25-45',
        'interested in fitness.',
        '',
        'The app avatar "Coach Alex" answers user questions in chat; the onboarding does not mention',
        'that Alex is an AI system. Ad visuals are AI-generated before/after photos of "real members" —',
        'the people shown do not exist, and there is no disclosure or content marking.',
        '',
        'We retarget users who viewed the pricing page up to 8 times per day across platforms for',
        '30 days. The "7-day free trial" auto-renews into an annual €199 plan; the renewal terms are',
        'in the FAQ but not shown at sign-up. Progress data (weight, body measurements) is used to',
        'personalise upsell offers.',
      ].join('\n'),
      channels: ['instagram', 'youtube'],
      target_audience: 'adults 25-45 interested in fitness',
      markets: ['EU'],
      uses_ai_generation: true,
      uses_personalisation: true,
    },
  },
  {
    label: 'Low-risk demo: "Museum Nights"',
    description: 'A largely compliant campaign — useful for contrast.',
    campaign: {
      title: 'Museum Nights — Summer Open Doors',
      text: [
        'Campaign for a city museum association promoting free late-night openings every Friday in',
        'July. Message: "Discover 12 museums, open until midnight, free entry — no registration',
        'needed." Channels: posters, local radio, and a city newsletter that people explicitly',
        'subscribed to, with a one-click unsubscribe link in every mail.',
        '',
        'Social ads on Instagram are clearly labelled "Sponsored — City Museums Association" and use',
        'only broad location targeting (city residents 18+), no behavioural profiles. All photos are',
        'real photographs credited to the photographer. The landing page collects no personal data.',
      ].join('\n'),
      channels: ['instagram', 'newsletter', 'out-of-home'],
      target_audience: 'city residents 18+',
      markets: ['EU'],
      uses_ai_generation: false,
      uses_personalisation: false,
    },
  },
];
