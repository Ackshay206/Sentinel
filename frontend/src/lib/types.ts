export type Capabilities = {
  deepgram: boolean;
  openai: boolean;
  elevenlabs: boolean;
  twilio: boolean;
};

export type Stage = 'benign' | 'authority' | 'urgency' | 'secrecy' | 'payment';

export type ServerMessage =
  | { type: 'ready'; capabilities: Capabilities }
  | { type: 'transcript'; text: string; is_final: boolean }
  | {
      type: 'risk';
      score: number;
      stage: Stage;
      highest_rank: number;
      scam_type: string;
      payment_vector?: string;
      red_flags: string[];
      confidence?: number;
      fired: boolean;
      should_fire: boolean;
      recommended_action?: string;
    }
  | {
      type: 'intervention';
      warning_text: string;
      sms_text: string;
      scam_type: string;
      score: number;
      red_flags: string[];
    }
  | { type: 'tts'; mime: string; text: string; audio_b64: string }
  | { type: 'sms'; sent: boolean; text: string }
  | { type: 'reset_ok' };

export type Classification = {
  scam_type: string;
  stage: Stage;
  confidence: number;
  red_flags: string[];
  recommended_action: string;
};
