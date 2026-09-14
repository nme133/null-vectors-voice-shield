import './ConversationAnalysis.css';

interface Signal {
  name: string;
  detected: boolean;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

interface ConversationAnalysisProps {
  signals: {
    authorityImpersonation: boolean;
    urgency: boolean;
    financialRequest: boolean;
    threatFear: boolean;
    instructionToTransfer: boolean;
  };
}

export const ConversationAnalysis: React.FC<ConversationAnalysisProps> = ({ signals }) => {
  const isIdle = !Object.values(signals).some(val => val === true);
  
  const analysisSignals: Signal[] = [
    {
      name: 'Authority Impersonation',
      detected: signals.authorityImpersonation,
      severity: signals.authorityImpersonation ? 'critical' : 'low'
    },
    {
      name: 'Urgency',
      detected: signals.urgency,
      severity: signals.urgency ? 'high' : 'low'
    },
    {
      name: 'Financial Request',
      detected: signals.financialRequest,
      severity: signals.financialRequest ? 'critical' : 'low'
    },
    {
      name: 'Threat / Fear',
      detected: signals.threatFear,
      severity: signals.threatFear ? 'high' : 'low'
    },
    {
      name: 'Instruction to Transfer Money',
      detected: signals.instructionToTransfer,
      severity: signals.instructionToTransfer ? 'critical' : 'low'
    }
  ];

  return (
    <div className="conversation-analysis">
      <div className="conv-analysis-header">
        <h2>Conversational Risk Signals</h2>
      </div>
      
      {isIdle ? (
        <div className="conv-analysis-idle">
          <div className="idle-message">WAITING FOR TRANSCRIPT</div>
          <p>Start monitoring to analyze conversation</p>
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
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
                  </svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                  </svg>
                )}
              </div>
              <div className="signal-name">{signal.name}</div>
              <div className={`signal-status ${signal.detected ? 'detected' : 'clear'}`}>
                {signal.detected ? 'DETECTED' : 'CLEAR'}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
