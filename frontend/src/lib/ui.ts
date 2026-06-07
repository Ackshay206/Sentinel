import type { Stage } from './types';

export const STAGE_ORDER: Stage[] = [
  'authority',
  'urgency',
  'secrecy',
  'payment',
];

export const STAGE_LABEL: Record<Stage, string> = {
  benign: 'All clear',
  authority: 'Claimed authority',
  urgency: 'Manufactured urgency',
  secrecy: 'Demand for secrecy',
  payment: 'Payment coercion',
};

export const SCAM_LABEL: Record<string, string> = {
  none: 'No scam',
  unknown: 'Unidentified scam',
  grandparent: 'Grandparent scam',
  bank_impersonation: 'Bank impersonation',
  irs_government: 'IRS / government',
  government_grant: 'Government-grant scam',
  tech_support: 'Tech support',
  refund: 'Refund scam',
  subscription_renewal: 'Subscription-renewal scam',
  delivery_package: 'Delivery / package',
  loan_debt: 'Loan / debt-relief',
  investment_crypto: 'Investment / crypto',
  pig_butchering: 'Pig butchering (romance)',
  prize_lottery: 'Prize / lottery',
  charity: 'Charity scam',
  auto_warranty: 'Auto warranty',
  job_employment: 'Job / work-from-home',
  utility_shutoff: 'Utility shutoff',
};

export const VECTOR_LABEL: Record<string, string> = {
  none: '',
  gift_card: 'gift cards',
  wire_transfer: 'wire transfer',
  crypto_wallet: 'crypto wallet',
  bank_or_card_details: 'bank / card details',
  otp_code: 'one-time passcode',
  upfront_fee: 'upfront fee',
  remote_access: 'remote access',
  courier_cash: 'cash courier',
};

function hex(n: number) {
  return Math.round(n).toString(16).padStart(2, '0');
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

// teal (#2fd6c3) → amber (#f5c451) → red (#ff4d5e) across 0..100
export function riskColor(score: number): string {
  const stops = [
    [0x2f, 0xd6, 0xc3],
    [0xf5, 0xc4, 0x51],
    [0xff, 0x4d, 0x5e],
  ];
  const s = Math.max(0, Math.min(100, score)) / 100;
  const seg = s < 0.5 ? 0 : 1;
  const t = s < 0.5 ? s / 0.5 : (s - 0.5) / 0.5;
  const a = stops[seg];
  const b = stops[seg + 1];
  return `#${hex(lerp(a[0], b[0], t))}${hex(lerp(a[1], b[1], t))}${hex(
    lerp(a[2], b[2], t),
  )}`;
}
