import React from 'react';
import './Header.css';

export type NavTab = 'overview' | 'analysis' | 'transcript' | 'events' | 'system' | 'settings';

interface HeaderProps {
  connectionStatus: 'online' | 'offline';
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  isMonitoring: boolean;
  isDemoMode: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  connectionStatus,
  activeTab,
  onSelectTab,
  isMonitoring,
  isDemoMode
}) => {
  const tabs: { id: NavTab; label: string }[] = [
    { id: 'overview', label: 'OVERVIEW' },
    { id: 'analysis', label: 'ANALYSIS' },
    { id: 'transcript', label: 'TRANSCRIPT' },
    { id: 'events', label: 'EVENTS' },
    { id: 'system', label: 'SYSTEM' },
    { id: 'settings', label: 'SETTINGS' }
  ];

  return (
    <header className="app-header">
      <div className="header-inner">
        {/* Brand */}
        <div className="header-brand-block">
          <div className="brand-logo-mark">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
          </div>
          <div className="brand-title-column">
            <div className="brand-name-row">
              <span className="brand-name">NULL VECTORS</span>
              <span className="brand-badge">VOICE SHIELD</span>
            </div>
            <span className="brand-tagline">AI IMPERSONATION DETECTION SYSTEM • SIH 2026</span>
          </div>
        </div>

        {/* Top Navigation Tabs */}
        <nav className="header-nav" aria-label="Main Navigation">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={`nav-tab-btn ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => onSelectTab(t.id)}
            >
              {t.label}
              {activeTab === t.id && <span className="tab-indicator-line" />}
            </button>
          ))}
        </nav>

        {/* Status Indicators */}
        <div className="header-status-block">
          {isDemoMode && (
            <div className="demo-mode-badge">
              <span className="demo-dot"></span>
              DEMO SIMULATION
            </div>
          )}

          <div className={`status-pill-badge ${connectionStatus}`}>
            <span className="status-dot"></span>
            <span className="status-text">
              {connectionStatus === 'online' ? 'BACKEND READY' : 'OFFLINE'}
            </span>
          </div>

          <div className={`mic-pill-badge ${isMonitoring ? 'recording' : 'standby'}`}>
            <span className="mic-dot"></span>
            <span>{isMonitoring ? 'INTAKE LIVE' : 'INTAKE IDLE'}</span>
          </div>
        </div>
      </div>
    </header>
  );
};
