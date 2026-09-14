import './VoiceAuthenticity.css';

interface VoiceAuthenticityProps {
  model: string;
  score: number;
  status: 'authentic' | 'spoof_suspected' | 'spoof_detected';
  confidence: string;
}

export const VoiceAuthenticity: React.FC<VoiceAuthenticityProps> = ({
  model,
  score,
  status,
  confidence
}) => {
  const isIdle = score === 0 && status === 'authentic';
  
  const statusLabel = {
    authentic: 'AUTHENTIC',
    spoof_suspected: 'SPOOF SUSPECTED',
    spoof_detected: 'SPOOF DETECTED'
  }[status];

  const statusDescription = {
    authentic: 'Voice characteristics match expected patterns for authentic voice.',
    spoof_suspected: 'Voice analysis detected anomalies consistent with voice cloning or synthesis.',
    spoof_detected: 'High confidence detection of synthetic or cloned voice.'
  }[status];

  return (
    <div className="voice-authenticity">
      <div className="voice-auth-header">
        <h2>Voice Authenticity</h2>
      </div>
      
      {isIdle ? (
        <div className="voice-auth-idle">
          <div className="idle-message">WAITING FOR AUDIO</div>
          <p>Start monitoring to begin voice analysis</p>
        </div>
      ) : (
        <>
          <div className={`voice-auth-status ${status}`}>
            {statusLabel}
          </div>
          
          <div className="voice-auth-details">
            <div className="detail-row">
              <div className="detail-label">Model</div>
              <div className="detail-value">{model}</div>
            </div>
            
            <div className="detail-row">
              <div className="detail-label">Authenticity Signal</div>
              <div className="detail-value score-bar">
                <div className="score-value">{score}</div>
                <div className="score-bar-container">
                  <div
                    className={`score-bar-fill ${status}`}
                    style={{ width: `${score}%` }}
                  ></div>
                </div>
              </div>
            </div>
            
            <div className="detail-row">
              <div className="detail-label">Confidence</div>
              <div className="detail-value">{confidence}</div>
            </div>
          </div>
          
          <div className="voice-auth-description">
            {statusDescription}
          </div>
          
          <div className="voice-auth-note">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>Model Score indicates the confidence level of voice analysis. Not a probability - use with other signals.</span>
          </div>
        </>
      )}
    </div>
  );
};
