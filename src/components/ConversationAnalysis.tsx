import React from 'react';
import './ConversationAnalysis.css';

interface Signal {
  name: string;
  detected: boolean;
  intensity: number; // display 0-100
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface ConversationAnalysisProps {
  signals: {
    authorityImpersonation?: boolean | number;
    urgency?: boolean | number;
    financialRequest?: boolean | number;
    threatFear?: boolean | number;
    instructionToTransfer?: boolean | number;
    credentialRequest?: boolean | number;
    otpRequest?: boolean | number;
    threat?: boolean | number;
    secrecy?: boolean | number;
    persuasion?: boolean | number;
    repeatedConfirmation?: boolean | number;
  };
  reasons?: string[];
  hasAnalysis?: boolean;
  recommendation?: string;
}

const isSignalDetected = (val: boolean | number | undefined, threshold = 30): { detected: boolean; intensity: number } => {
  if (typeof val === 'boolean') {
    return { detected: val, intensity: val ? 85 : 0 };
  }
  if (typeof val === 'number') {
    const intensity = val <= 1 ? val * 100 : val;
    return { detected: intensity > threshold, intensity };
  }
  return { detected: false, intensity: 0 };
};

export const ConversationAnalysis: React.FC<ConversationAnalysisProps> = ({ signals, reasons, hasAnalysis = false, recommendation }) => {
  const authSig = isSignalDetected(signals.authorityImpersonation);
  const urgSig = isSignalDetected(signals.urgency);
  const finSig = isSignalDetected(signals.financialRequest);
  const threatSig = isSignalDetected(signals.threatFear ?? signals.threat);
  const credSig = isSignalDetected(signals.credentialRequest);
  const otpSig = isSignalDetected(signals.otpRequest);
  const secrecySig = isSignalDetected(signals.secrecy);
  const persuasionSig = isSignalDetected(signals.persuasion);
  const confirmSig = isSignalDetected(signals.repeatedConfirmation);
  const transferSig = isSignalDetected(
    signals.instructionToTransfer ?? (finSig.detected && finSig.intensity > 60 ? 1 : 0)
  );

  const isIdle = !hasAnalysis;

  const analysisSignals: Signal[] = [
    {
      name: 'Urgency / Time Pressure',
      detected: urgSig.detected,
      intensity: urgSig.intensity,
      severity: urgSig.detected ? 'high' : 'low'
    },
    {
      name: 'Financial Action / Transfer',
      detected: finSig.detected,
      intensity: finSig.intensity,
      severity: finSig.detected ? 'critical' : 'low'
    },
    {
      name: 'Instruction to Divert Funds',
      detected: transferSig.detected,
      intensity: transferSig.intensity,
      severity: transferSig.detected ? 'critical' : 'low'
    },
    {
      name: 'Secrecy / "Don\'t Discuss"',
      detected: secrecySig.detected,
      intensity: secrecySig.intensity,
      severity: secrecySig.detected ? 'high' : 'low'
    },
    {
      name: 'Social Engineering / Manipulation',
      detected: persuasionSig.detected,
      intensity: persuasionSig.intensity,
      severity: persuasionSig.detected ? 'high' : 'low'
    },
    {
      name: 'Repeated Confirmation / Pressure',
      detected: confirmSig.detected,
      intensity: confirmSig.intensity,
      severity: confirmSig.detected ? 'critical' : 'low'
    },
    {
      name: 'Authority Impersonation',
      detected: authSig.detected,
      intensity: authSig.intensity,
      severity: authSig.detected ? 'critical' : 'low'
    },
    {
      name: 'Credential / Account Request',
      detected: credSig.detected || otpSig.detected,
      intensity: Math.max(credSig.intensity, otpSig.intensity),
      severity: credSig.detected || otpSig.detected ? 'critical' : 'low'
    },
    {
      name: 'Coercion / Threat / Intimidation',
      detected: threatSig.detected,
      intensity: threatSig.intensity,
      severity: threatSig.detected ? 'high' : 'low'
    }
  ];

  return (
    <div className="conversation-analysis">
      <div className="conv-analysis-header">
        <div className="conv-title-row">
          <span className="conv-icon-badge">🧠</span>
          <h2>Conversational Intent Signals (GPT-OSS)</h2>
        </div>
        <span className="model-chip">NLP Vector Engine</span>
      </div>

      {isIdle ? (
        <div className="conv-analysis-idle">
          <div className="idle-message">AWAITING SPEECH TRANSCRIPT</div>
          <p>Linguistic analysis model will extract social engineering and pressure vectors in real time.</p>
        </div>
      ) : (
        <div className="signals-list">
          {analysisSignals.map((signal) => (
            <div
              key={signal.name}
              className={`signal-item ${signal.detected ? 'detected' : 'not-detected'} ${signal.severity}`}
            >
              <div className="signal-indicator">
                {signal.detected ? (
                  <span className="signal-dot-detected">●</span>
                ) : (
                  <span className="signal-dot-clear">○</span>
                )}
              </div>
              <div className="signal-meta">
                <div className="signal-name">{signal.name}</div>
                {signal.detected && (
                  <div className="signal-intensity-bar">
                    <div
                      className={`signal-intensity-fill ${signal.severity}`}
                      style={{ width: `${Math.max(20, Math.min(100, signal.intensity))}%` }}
                    />
                  </div>
                )}
              </div>
              <div className={`signal-status ${signal.detected ? 'detected' : 'clear'}`}>
                {signal.detected ? `DETECTED (${Math.round(signal.intensity)}%)` : 'CLEAR'}
              </div>
            </div>
          ))}

          {reasons && reasons.length > 0 && (
            <div className="conv-reasons-block">
              <div className="conv-reasons-title">MODEL-REPORTED EVIDENCE</div>
              {reasons.map((reason, idx) => (
                <div key={`${reason}-${idx}`} className="conv-reason-item">
                  <span className="conv-reason-bullet">▪</span>
                  <span className="conv-reason-text">{reason}</span>
                </div>
              ))}
            </div>
          )}

          {recommendation && recommendation.trim() && (
            <div className="conv-reasons-block conv-recommendation-block">
              <div className="conv-reasons-title">RECOMMENDED ACTION</div>
              <div className="conv-reason-item">
                <span className="conv-reason-bullet">⚠</span>
                <span className="conv-reason-text">{recommendation}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};