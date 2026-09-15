import React, { useCallback, useRef } from 'react';
import { useFileAnalysis } from '../backend/useFileAnalysis';
import { ACCEPTED_AUDIO_EXTENSIONS } from '../backend/uploadTypes';
import { RiskFactor } from '../data/mockData';
import { VoiceAuthenticity } from './VoiceAuthenticity';
import { ConversationAnalysis } from './ConversationAnalysis';
import { RiskFactors } from './RiskFactors';
import { HeroRiskGauge } from './HeroRiskGauge';
import { RecommendedAction } from './RecommendedAction';
import './AudioFileUpload.css';

export interface AudioFileUploadProps {
  language: string;
  disabled?: boolean;
}

const STAGE_LABELS: Record<string, string> = {
  file_received: 'Audio file received',
  audio_decoded: 'Audio decoded to PCM',
  normalized_16khz: 'Normalized to 16 kHz / mono / Float32',
  spectra_started: 'Spectra-AASIST3 inference started',
  spectra_finished: 'Spectra-AASIST3 inference finished',
  whisper_started: 'Whisper transcription started',
  whisper_finished: 'Whisper transcription finished',
  gpt_started: 'GPT-OSS conversational analysis started',
  gpt_finished: 'GPT-OSS conversational analysis finished',
  risk_calculated: 'Risk score calculated',
};

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const STAGE_ORDER = Object.keys(STAGE_LABELS);

export const AudioFileUpload: React.FC<AudioFileUploadProps> = ({ language, disabled }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const { status, selectedFile, stages, result, error, analyze, reset } = useFileAnalysis();

  const handlePick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (file) {
        analyze(file, language);
      }
    },
    [analyze, language]
  );

  const isBusy = status === 'uploading' || status === 'processing';
  const isFinished = status === 'done' && result;
  const orderedStages = STAGE_ORDER.filter((name) => stages.some((s) => s.stage === name));

  const riskFactors: RiskFactor[] = (result?.risk.reasons ?? []).map((reason, idx) => ({
    id: `upload-factor-${idx}`,
    name: reason,
    status: 'detected' as const,
    description:
      'Reported by the real risk engine from acoustic and conversational analysis of the uploaded audio file.',
  }));

  return (
    <div className="upload-audio-panel">
      <div className="upload-audio-header">
        <div className="upload-title-group">
          <span className="upload-icon-glyph">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </span>
          <h3 className="upload-title">UPLOAD AUDIO ANALYSIS</h3>
        </div>

        <div className="upload-mode-pill">
          <span className={`upload-mode-dot ${isBusy ? 'busy' : isFinished ? 'online' : 'offline'}`}></span>
          <span className="upload-mode-label">OFFLINE FILE MODE</span>
        </div>
      </div>

      {/* Dropzone / picker row */}
      <div className="upload-picker-row">
        <button
          type="button"
          className="upload-audio-btn"
          onClick={handlePick}
          disabled={disabled || isBusy}
          title="Choose a WAV, MP3, M4A, OGG, WEBM or FLAC file"
        >
          <span className="btn-icon">📁</span>
          {isBusy ? (status === 'uploading' ? 'UPLOADING…' : 'ANALYZING…') : 'UPLOAD AUDIO'}
        </button>
        <span className="upload-accept-hint">WAV • MP3 • M4A • OGG • WEBM • FLAC</span>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_AUDIO_EXTENSIONS}
          onChange={handleFileChange}
          className="upload-file-input"
          aria-label="Upload audio file"
        />
      </div>

      {selectedFile && (
        <div className="upload-file-detail">
          <div className="upload-file-name">
            <span className="detail-lbl">FILE:</span>
            <span className="detail-val mono">{selectedFile.name}</span>
          </div>
          <div className="upload-file-meta">
            <span className="file-meta-chip">{formatBytes(selectedFile.size)}</span>
            {selectedFile.type && <span className="file-meta-chip">{selectedFile.type}</span>}
          </div>
        </div>
      )}

      {/* Status / stage trace (real backend progress, no fabricated percentages) */}
      {selectedFile && !isFinished && !error && (
        <div className="upload-stages">
          <div className="upload-status-line">
            <span className={`status-spinner ${isBusy ? 'spin' : ''}`}></span>
            <span className="upload-status-text">
              {status === 'uploading'
                ? 'Uploading file to backend…'
                : status === 'processing'
                  ? 'Analyzing uploaded audio through the real pipeline…'
                  : status === 'done'
                    ? 'Backend finished without a usable result.'
                    : 'Awaiting file selection'}
            </span>
          </div>

          {orderedStages.length > 0 && (
            <ol className="upload-stage-list">
              {orderedStages.map((name) => {
                const stage = stages.find((s) => s.stage === name)!;
                const isLast = name === orderedStages[orderedStages.length - 1] && isBusy;
                return (
                  <li key={name} className={`upload-stage ${isLast ? 'active' : 'complete'}`}>
                    <span className="stage-dot"></span>
                    <span className="stage-label">{STAGE_LABELS[name]}</span>
                    <span className="stage-detail mono">{stage.message}</span>
                    <span className="stage-elapsed mono">
                      {stage.elapsed.toFixed(1)}s
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}

      {error && (
        <div className="upload-error-banner" role="alert">
          <span className="error-icon">⚠</span>
          <p>{error}</p>
        </div>
      )}

      {/* Real results from the real backend models */}
      {isFinished && result && (
        <div className="upload-results">
          <div className="upload-results-title">
            <span className="results-badge">COMPLETE</span>
            <span className="results-sub">Real Spectra-AASIST3 + Whisper + GPT-OSS + Risk Engine fusion</span>
          </div>

          <VoiceAuthenticity
            model={result.voice_analysis.model}
            score={result.voice_analysis.score}
            status={result.voice_analysis.status}
            confidence={result.voice_analysis.confidence}
            isSpoof={result.voice_analysis.is_spoof}
          />

          <div className="upload-spectra-raw">
            <span className="upload-spectra-raw-label mono">
              RAW BONAFIDE LOGIT
            </span>
            <span className="upload-spectra-raw-value mono">{result.voice_analysis.raw_bonafide_logit}</span>
            <span className="upload-spectra-raw-note">
              higher = more bona-fide-like · lower = more spoof-like · NOT a probability
            </span>
            <span className="upload-spectra-windows mono">
              {result.voice_analysis.windows_analyzed} window(s) ·{' '}
              {result.voice_analysis.spoof_windows} spoof · {result.voice_analysis.bonafide_windows} bonafide
            </span>
          </div>

          {/* Transcript */}
          <div className="upload-transcript-block">
            <div className="upload-transcript-header">
              <span className="upload-block-eyebrow">TRANSCRIPT</span>
              <span className="lang-chip mono">
                {result.transcript.language === 'auto' ? 'WHISPER AUTO-DETECT' : `LANG: ${result.transcript.language.toUpperCase()}`}
              </span>
            </div>
            {result.transcript.text ? (
              <p className="upload-transcript-text">“{result.transcript.text}”</p>
            ) : (
              <p className="upload-transcript-empty">
                No transcript produced — Whisper found no meaningful speech (the transcript is never translated).
              </p>
            )}
          </div>

          <ConversationAnalysis
            signals={{
              urgency: result.conversation.urgency,
              authorityImpersonation: result.conversation.authority_impersonation,
              financialRequest: result.conversation.financial_request,
              threat: result.conversation.threat,
              credentialRequest: result.conversation.credential_request,
              otpRequest: result.conversation.otp_request,
              secrecy: result.conversation.secrecy,
              persuasion: result.conversation.persuasion,
              repeatedConfirmation: result.conversation.repeated_confirmation,
            }}
            reasons={result.conversation.reasons}
          />

          {/* Overall risk + recommendation */}
          <div className="upload-risk-block">
            <div className="upload-block-eyebrow">OVERALL RISK</div>
            <HeroRiskGauge
              score={result.risk.risk_score}
              level={result.risk.risk_level}
              isActive={true}
            />
            <div className="upload-risk-components">
              <div className="component-cell">
                <span className="component-key">VOICE</span>
                <span className="component-val mono">{result.risk.voice_score}</span>
                <span className="component-cap">/40</span>
              </div>
              <div className="component-cell">
                <span className="component-key">SOCIAL</span>
                <span className="component-val mono">{result.risk.social_score}</span>
                <span className="component-cap">/40</span>
              </div>
              <div className="component-cell">
                <span className="component-key">ACTION</span>
                <span className="component-val mono">{result.risk.action_score}</span>
                <span className="component-cap">/20</span>
              </div>
            </div>
          </div>

          <RiskFactors factors={riskFactors} />

          <RecommendedAction
            action={result.risk.recommendation}
            description="Recommended by the real-time risk engine from the uploaded audio file's acoustic and conversational signals."
          />
        </div>
      )}

      {isFinished && (
        <button type="button" className="upload-clear-btn" onClick={reset}>
          CLEAR UPLOAD RESULTS
        </button>
      )}
    </div>
  );
};