export const BACKEND_UPLOAD_URL =
  import.meta.env.VITE_UPLOAD_URL ?? 'http://localhost:8000/api/v1/analyze/upload';

export const ACCEPTED_AUDIO_EXTENSIONS = '.wav,.mp3,.m4a,.ogg,.webm,.flac,.aac,.opus';

export type UploadStageName =
  | 'file_received'
  | 'audio_decoded'
  | 'normalized_16khz'
  | 'spectra_started'
  | 'spectra_finished'
  | 'whisper_started'
  | 'whisper_finished'
  | 'gpt_started'
  | 'gpt_finished'
  | 'risk_calculated';

export interface UploadStageEvent {
  type: 'stage';
  stage: UploadStageName;
  /** Real stage detail from the backend (counts, sample rates, timings). */
  message: string;
  /** Seconds since the analysis began (real backend measurement). */
  elapsed: number;
}

export interface UploadFileInfo {
  filename: string;
  size_bytes: number;
  sample_rate: number;
  channels: number;
  duration_seconds: number;
}

export interface UploadVoiceAnalysis {
  score: number;
  is_spoof: boolean;
  confidence: string;
  model: string;
  status: 'spoof' | 'suspicious' | 'bona_fide' | 'insufficient_speech';
  raw_bonafide_logit: number;
  windows_analyzed: number;
  spoof_windows: number;
  bonafide_windows: number;
}

export interface UploadTranscript {
  text: string;
  language: string;
  chars: number;
}

export interface UploadConversation {
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

export interface UploadRisk {
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  voice_score: number;
  social_score: number;
  action_score: number;
  reasons: string[];
  recommendation: string;
}

export interface UploadResult {
  type: 'result';
  file: UploadFileInfo;
  voice_analysis: UploadVoiceAnalysis;
  transcript: UploadTranscript;
  conversation: UploadConversation;
  risk: UploadRisk;
  timing: Record<string, number>;
}

export interface UploadErrorEvent extends Error {
  type: 'error';
  code: string;
}

export type UploadStreamEvent = UploadStageEvent | UploadResult | UploadErrorEvent;

export type UploadStatus = 'idle' | 'uploading' | 'processing' | 'done' | 'error';