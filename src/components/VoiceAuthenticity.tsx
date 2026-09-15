import React from 'react';
import './VoiceAuthenticity.css';

export interface VoiceAuthenticityProps {
  model?: string;
  score?: number;
  status?: 'spoof' | 'suspicious' | 'bona_fide' | 'insufficient_speech';
  confidence?: string;
  isSpoof?: boolean;
}

type ResolvedStatus = 'authentic' | 'spoof_suspected' | 'spoof_detected' | 'insufficient_speech';

export const VoiceAuthenticity: React.FC<VoiceAuthenticityProps> = ({
  model = 'Spectra-AASIST3',
  score = 0,
  status,
  confidence,
  isSpoof
}) => {
  // Trust the backend voice-authenticity verdict.  The backend only commits
  // to 'spoof' / 'bona_fide' after consecutive windows agree, and deliberately
  // reports 'suspicious' / 'insufficient_speech' in between.  Color and label
  // are derived from THIS status only — never from the fused overall risk.
  // The legacy score/isSpoof heuristic applies only before the first verdict
  // arrives (idle / demo mock data) and never overrides a live `status`.
  const resolvedStatus: ResolvedStatus =
    status === 'spoof'
      ? 'spoof_detected'
      : status === 'suspicious'
        ? 'spoof_suspected'
        : status === 'insufficient_speech'
          ? 'insufficient_speech'
          : status === 'bona_fide'
            ? 'authentic'
            : score >= 75 || (isSpoof && score >= 70)
              ? 'spoof_detected'
              : score >= 35 || isSpoof
                ? 'spoof_suspected'
                : 'authentic';

  const resolvedConfidence = confidence || (score > 0 ? `Spoof signal index: ${Math.round(score)}/100` : 'Standby');
  const isIdle = score === 0 && resolvedStatus === 'authentic';

  const statusLabel = {
    authentic: 'LIKELY HUMAN',
    spoof_suspected: 'SUSPICIOUS',
    spoof_detected: 'POSSIBLE AI / SPOOF',
    insufficient_speech: 'NO SPEECH / INSUFFICIENT DATA'
  }[resolvedStatus];

  const statusDescription = {
    authentic: 'Audio phase coherence and spectral harmonics match authentic human vocalization patterns.',
    spoof_suspected: 'Acoustic anomalies detected in the voice signal. More consistent windows are required before committing to an AI/spoof verdict.',
    spoof_detected: 'High-confidence acoustic spoofing detected. Characteristic signatures of deepfake neural vocoder synthesis.',
    insufficient_speech: 'No clear speech in the current window. Silence is not evidence of a human voice.'
  }[resolvedStatus];

  return (
    <div className="voice-authenticity">
      <div className="voice-auth-header">
        <div className="auth-title-row">
          <span className="auth-icon-badge">🎙</span>
          <h2>Acoustic Biometric Verification</h2>
        </div>
        <span className="model-chip">{model}</span>
      </div>

      {isIdle ? (
        <div className="voice-auth-idle">
          <div className="idle-message">AWAITING LIVE AUDIO</div>
          <p>Spectra-AASIST3 will analyze incoming vocal timbre, glottal pulses, and phase coherence.</p>
        </div>
      ) : (
        <>
          <div className={`voice-auth-status ${resolvedStatus}`}>
            <span className="status-marker-dot"></span>
            {statusLabel}
          </div>

          <div className="voice-auth-details">
            <div className="detail-row">
              <div className="detail-label">Biometric Model</div>
              <div className="detail-value mono-val">{model}</div>
            </div>

            <div className="detail-row">
              <div className="detail-label">Spoof Signal</div>
              <div className="detail-value score-bar">
                <div className="score-value mono-val">{score}%</div>
                <div className="score-bar-container">
                  <div
                    className={`score-bar-fill ${resolvedStatus}`}
                    style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
                  ></div>
                </div>
              </div>
            </div>

            <div className="detail-row">
              <div className="detail-label">Evaluation Confidence</div>
              <div className="detail-value mono-val">{resolvedConfidence}</div>
            </div>
          </div>

          <div className="voice-auth-description">
            {statusDescription}
          </div>

          <div className="voice-auth-note">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>The percentage is a 0-100 spoof signal strength for display only — it is not a probability. Color reflects the Spectra-AASIST3 authenticity verdict, distinct from the fused Overall Threat Risk.</span>
          </div>
        </>
      )}
    </div>
  );
};