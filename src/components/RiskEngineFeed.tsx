import React, { useEffect, useRef } from 'react';
import { RiskFeedEvent } from '../data/mockData';
import './RiskEngineFeed.css';

interface RiskEngineFeedProps {
  events: RiskFeedEvent[];
  recommendation: {
    action: string;
    description: string;
  };
  isActive: boolean;
}

export const RiskEngineFeed: React.FC<RiskEngineFeedProps> = ({
  events,
  recommendation,
  isActive
}) => {
  const feedEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  const renderIcon = (severity: RiskFeedEvent['severity']) => {
    switch (severity) {
      case 'success':
        return <span className="event-icon icon-success">✓</span>;
      case 'warning':
        return <span className="event-icon icon-warning">⚠</span>;
      case 'critical':
        return <span className="event-icon icon-critical">●</span>;
      case 'info':
      default:
        return <span className="event-icon icon-info">ℹ</span>;
    }
  };

  return (
    <div className="risk-engine-panel">
      {/* Header */}
      <div className="risk-engine-header">
        <div className="header-left">
          <div className={`status-blip ${isActive ? 'active' : 'idle'}`}></div>
          <h2 className="panel-title">RISK ENGINE</h2>
        </div>
        <div className="header-badge">
          <span className="badge-feed-count">{events.length} SIGNALS</span>
          <span className="badge-stream-type">LIVE FEED</span>
        </div>
      </div>

      {/* Security Event Stream */}
      <div className="event-stream-container">
        {events.length === 0 ? (
          <div className="event-stream-empty">
            <div className="empty-radar-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z" opacity="0.3"/>
                <path d="M12 6a6 6 0 1 0 6 6 6 6 0 0 0-6-6zm0 10a4 4 0 1 1 4-4 4 4 0 0 1-4 4z" opacity="0.6"/>
                <circle cx="12" cy="12" r="2" fill="currentColor"/>
                <path d="M12 12L19 5" strokeWidth="2"/>
              </svg>
            </div>
            <p className="empty-primary">Risk Engine Standing By</p>
            <p className="empty-secondary">
              {isActive ? 'Awaiting incoming acoustic & conversational signals...' : 'Start monitoring or run Demo to stream threat events'}
            </p>
          </div>
        ) : (
          <div className="event-stream-list">
            {events.map((evt) => (
              <div key={evt.id} className={`event-card severity-${evt.severity}`}>
                <div className="event-icon-column">
                  {renderIcon(evt.severity)}
                </div>
                <div className="event-details">
                  <div className="event-meta">
                    <span className="event-timestamp">{evt.timestamp}</span>
                    {evt.source && <span className="event-source">[{evt.source.toUpperCase()}]</span>}
                  </div>
                  <div className="event-message">{evt.message}</div>
                </div>
              </div>
            ))}
            <div ref={feedEndRef} />
          </div>
        )}
      </div>

      {/* Recommended Action Bottom Card */}
      <div className="action-recommendation-block">
        <div className="recommendation-header">
          <span className="rec-eyebrow">RECOMMENDED ACTION</span>
          <span className={`rec-tag ${recommendation.action ? 'urgent' : 'standby'}`}>
            {recommendation.action ? 'ACTION REQUIRED' : 'STANDBY'}
          </span>
        </div>

        {recommendation.action ? (
          <div className="action-content-active">
            <div className="action-title-row">
              <span className="alert-shield-icon">🛡</span>
              <h3 className="action-title">{recommendation.action}</h3>
            </div>
            <p className="action-desc">{recommendation.description}</p>
          </div>
        ) : (
          <div className="action-content-idle">
            <p className="action-desc-idle">
              System monitoring active channels. Immediate protective recommendations will appear here upon threat detection.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
