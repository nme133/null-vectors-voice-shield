import './SystemStatus.css';

interface SystemStatusProps {
  components: {
    voiceAnalysis: 'active' | 'inactive';
    speechTranscription: 'active' | 'inactive';
    conversationAnalysis: 'active' | 'inactive';
    riskEngine: 'active' | 'inactive';
  };
}

export const SystemStatus: React.FC<SystemStatusProps> = ({ components }) => {
  const statusItems = [
    {
      name: 'Spectra-AASIST3',
      label: 'Voice Analysis',
      status: components.voiceAnalysis
    },
    {
      name: 'Whisper',
      label: 'Speech Transcription',
      status: components.speechTranscription
    },
    {
      name: 'GPT-OSS',
      label: 'Conversation Analysis',
      status: components.conversationAnalysis
    },
    {
      name: 'Risk Engine',
      label: 'Risk Calculation',
      status: components.riskEngine
    }
  ];

  return (
    <div className="system-status">
      <div className="system-status-header">
        <h2>System Status</h2>
      </div>
      
      <div className="status-components">
        {statusItems.map((item) => (
          <div
            key={item.label}
            className={`status-component ${item.status}`}
          >
            <div className="component-indicator">
              <div className={`indicator-dot ${item.status}`}></div>
            </div>
            <div className="component-info">
              <div className="component-name">{item.name}</div>
              <div className="component-label">{item.label}</div>
            </div>
            <div className={`component-status ${item.status}`}>
              {item.status === 'active' ? 'ACTIVE' : 'INACTIVE'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
