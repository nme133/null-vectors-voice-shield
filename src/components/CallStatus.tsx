import './CallStatus.css';

interface CallStatusProps {
  callStatus: 'live' | 'ended' | 'idle';
  callDuration: number;
  callerIdentity: string;
  audioStreamActive: boolean;
}

const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

export const CallStatus: React.FC<CallStatusProps> = ({
  callStatus,
  callDuration,
  callerIdentity,
  audioStreamActive
}) => {
  return (
    <div className="call-status">
      <div className="call-status-header">
        <h2>Call Status</h2>
      </div>
      
      <div className="call-status-grid">
        <div className="status-item">
          <div className="status-label">Status</div>
          <div className={`status-value ${callStatus}`}>
            {callStatus.toUpperCase()}
          </div>
        </div>
        
        <div className="status-item">
          <div className="status-label">Duration</div>
          <div className="status-value">{formatDuration(callDuration)}</div>
        </div>
        
        <div className="status-item">
          <div className="status-label">Caller</div>
          <div className="status-value">{callerIdentity}</div>
        </div>
        
        <div className="status-item">
          <div className="status-label">Audio Stream</div>
          <div className={`status-value ${audioStreamActive ? 'active' : 'inactive'}`}>
            {audioStreamActive ? 'ACTIVE' : 'INACTIVE'}
          </div>
        </div>
      </div>
    </div>
  );
};
