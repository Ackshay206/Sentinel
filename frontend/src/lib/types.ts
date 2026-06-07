export type Capabilities = {
  deepgram: boolean;
  openai: boolean;
  elevenlabs: boolean;
  twilio: boolean;
  hume: boolean;
};

export type Stage = 'benign' | 'authority' | 'urgency' | 'secrecy' | 'payment';

export type ServerMessage =
  | { type: 'ready'; capabilities: Capabilities }
  | { type: 'transcript'; text: string; is_final: boolean; speaker?: number | null; label?: string }
  | { type: 'caller_ready' }
  | { type: 'input_role'; role: 'victim' | 'caller' }
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
  | { type: 'emotion'; stress: number; emotions: Record<string, number> }
  | { type: 'mode'; mode: Mode; reason?: string }
  | { type: 'agent_audio'; audio_b64: string; sample_rate: number }
  | { type: 'takeover_msg'; role: 'agent' | 'caller'; text: string }
  | { type: 'reset_ok' };

export type Mode = 'monitoring' | 'warning' | 'takeover';

export type Classification = {
  scam_type: string;
  stage: Stage;
  confidence: number;
  red_flags: string[];
  recommended_action: string;
};
