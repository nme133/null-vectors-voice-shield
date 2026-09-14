import './Header.css';

interface HeaderProps {
  connectionStatus: 'online' | 'offline';
}

export const Header: React.FC<HeaderProps> = ({ connectionStatus }) => {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-brand">
          <h1 className="header-title">VoxShield</h1>
          <p className="header-subtitle">Real-Time Voice Impersonation Detection</p>
        </div>
        <div className="header-status">
          <div className={`connection-indicator ${connectionStatus}`}>
            <span className="status-dot"></span>
            <span className="status-text">
              {connectionStatus === 'online' ? 'SYSTEM ONLINE' : 'SYSTEM OFFLINE'}
            </span>
          </div>
          <div className="mic-indicator">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v12a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="23"></line>
              <line x1="8" y1="23" x2="16" y2="23"></line>
            </svg>
            <span>Live</span>
          </div>
        </div>
      </div>
    </header>
  );
};
