import React from 'react';
import './VoiceAuthenticityMini.css';

export interface VoiceAuthenticityMiniProps {
  score: number;
  isSpoof: boolean;
  status?: 'spoof' | 'suspicious' | 'bona_fide' | 'insufficient_speech';
}

type VoiceAuthState = 'standby' | 'human' | 'suspicious' | 'spoof' | 'listening';

const STATUS_LABEL: Record<VoiceAuthState, string> = {
  standby: 'AWAITING LIVE AUDIO',
  human: 'LIKELY HUMAN',
  suspicious: 'SUSPICIOUS',
  spoof: 'POSSIBLE AI / SPOOF',
  listening: 'INSUFFICIENT SPEECH'
};

const STATUS_DESCRIPTION: Record<VoiceAuthState, string> = {
  standby: 'Acoustic voice analysis will start when audio is received.',
  human: 'Voice signal matches authentic human acoustic patterns.',
  suspicious: 'Acoustic anomalies detected in the voice signal.',
  spoof: 'Strong synthetic or cloned voice characteristics detected.',
  listening: 'No clear speech in the window. Silence is not evidence of a human voice.'
};

export const VoiceAuthenticityMini: React.FC<VoiceAuthenticityMiniProps> = ({
  score,
  isSpoof,
  status
}) => {
  const normalizedScore = Math.max(0, Math.min(100, score));

  // Trust the backend three-way verdict.  The backend only commits to
  // 'spoof' / 'bona_fide' after consecutive windows agree (small temporal
  // persistence); everything in between is 'suspicious'.  The color is
  // derived ONLY from the acoustic voice-authenticity status — never from
  // the numeric score and never from the overall risk gauge.  When no
  // status has arrived yet (e.g. demo mock data), fall back to the legacy
  // isSpoof/score heuristic.
  let state: VoiceAuthState;
  if (!status) {
    if (isSpoof && normalizedScore >= 75) state = 'spoof';
    else if (isSpoof || normalizedScore >= 35) state = 'suspicious';
    else if (normalizedScore === 0) state = 'standby';
    else state = 'human';
  } else if (status === 'insufficient_speech') {
    state = 'listening';
  } else if (status === 'spoof') {
    state = 'spoof';
  } else if (status === 'suspicious') {
    state = 'suspicious';
  } else {
    state = 'human';
  }

  return (
    <div className={`voice-auth-mini ${state}`}>
      <div className="vam-header">
        <span className="vam-title">VOICE AUTHENTICITY</span>
        <span className="vam-badge">ACOUSTIC</span>
      </div>

      <div className="vam-status-row">
        <span className="vam-dot"></span>
        <span className="vam-status-label">{STATUS_LABEL[state]}</span>
      </div>

      <div className="vam-meter">
        <div className="vam-meter-track">
          <div
            className={`vam-meter-fill ${state}`}
            style={{ width: `${normalizedScore}%` }}
          ></div>
        </div>
        <div className="vam-meter-scale">
          <span>HUMAN</span>
          <span>SPOOF</span>
        </div>
      </div>

      <div className="vam-score-row">
        {state === 'listening' || state === 'standby' ? (
          <>
            <span className="vam-score vam-score-idle">—</span>
            <span className="vam-score-caption">AWAITING VOICE SIGNAL</span>
          </>
        ) : (
          <>
            <span className="vam-score mono-val">{Math.round(normalizedScore)}</span>
            <span className="vam-score-caption">SPOOF SIGNAL INDEX (0-100)</span>
          </>
        )}
      </div>

      <p className="vam-description">{STATUS_DESCRIPTION[state]}</p>

      <div className="vam-note">
        Acoustic signal only; distinct from the fused Overall Threat Risk. Index is a
        normalized spoof strength, not a probability.
      </div>
    </div>
  );
};