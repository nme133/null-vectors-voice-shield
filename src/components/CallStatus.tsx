import React from 'react';
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
    <div className="call-status-bar">
      <div className="status-metric-cell">
        <span className="metric-label">CALL SESSION</span>
        <div className="metric-value-row">
          <span className={`status-pill ${callStatus}`}>
            <span className="pill-dot"></span>
            {callStatus.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="status-metric-cell">
        <span className="metric-label">ELAPSED TIME</span>
        <span className="metric-mono-val">{formatDuration(callDuration)}</span>
      </div>

      <div className="status-metric-cell caller-cell">
        <span className="metric-label">CALLER IDENTIFIER</span>
        <span className={`caller-id-val ${callerIdentity.includes('FLAGGED') ? 'flagged' : ''}`}>
          {callerIdentity}
        </span>
      </div>

      <div className="status-metric-cell">
        <span className="metric-label">AUDIO CHANNEL</span>
        <span className={`channel-pill ${audioStreamActive ? 'active' : 'idle'}`}>
          {audioStreamActive ? 'ACTIVE STREAM' : 'MUTED / INACTIVE'}
        </span>
      </div>
    </div>
  );
};
