export const BACKEND_WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/api/v1/stream';

export type BackendConnectionStatus = 'connecting' | 'open' | 'closed' | 'error';

export interface ConnectedMessage {
  type: 'connected';
  message: string;
  device: string;
  spectra_loaded: boolean;
  demo_mode: boolean;
}

export interface EventMessage {
  type: 'event';
  id: string;
  timestamp: string;
  message: string;
  severity: 'info' | 'warning' | 'critical' | 'success';
  source: 'audio' | 'voice' | 'nlp' | 'engine';
}

export interface VoiceAnalysisMessage {
  type: 'voice_analysis';
  score: number;
  is_spoof: boolean;
  confidence: string;
  model: string;
  raw_bonafide_logit: number;
  status?: 'spoof' | 'suspicious' | 'bona_fide' | 'insufficient_speech';
}

export interface TranscriptMessage {
  type: 'transcript';
  id: string;
  timestamp: string;
  speaker: 'caller';
  text: string;
}

export interface ConversationAnalysisMessage {
  type: 'conversation_analysis';
  urgency: number;
  authority_impersonation: number;
  financial_request: number;
  credential_request: number;
  otp_request: number;
  threat: number;
  secrecy: number;
  persuasion: number;
  repeated_confirmation: number;
  confidence: number;
  reasons: string[];
}

export interface RiskUpdateMessage {
  type: 'risk_update';
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  voice_score: number;
  social_score: number;
  action_score: number;
  reasons: string[];
  recommendation: string;
}

export interface ErrorMessage {
  type: 'error';
  message: string;
  code: string;
}

export interface StatusMessage {
  type: 'status';
  message: string;
  components: Record<string, string>;
}

export interface PongMessage {
  type: 'pong';
}

export type BackendStreamMessage =
  | ConnectedMessage
  | EventMessage
  | VoiceAnalysisMessage
  | TranscriptMessage
  | ConversationAnalysisMessage
  | RiskUpdateMessage
  | ErrorMessage
  | StatusMessage
  | PongMessage;

export interface UseBackendStreamOptions {
  url?: string;
  onStatusChange?: (status: BackendConnectionStatus, info?: { error?: string }) => void;
  onMessage?: (message: BackendStreamMessage) => void;
}
