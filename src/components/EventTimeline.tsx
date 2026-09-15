import React from 'react';
import { RiskFeedEvent } from '../data/mockData';
import './EventTimeline.css';

export interface LegacyTimelineEvent {
  timestamp: string;
  message: string;
  type?: 'info' | 'warning' | 'critical';
  id?: string;
}

export type AnyTimelineEvent = RiskFeedEvent | LegacyTimelineEvent;

interface EventTimelineProps {
  events: AnyTimelineEvent[];
}

export const EventTimeline: React.FC<EventTimelineProps> = ({ events }) => {
  const isIdle = events.length === 0;

  return (
    <div className="event-timeline">
      <div className="timeline-header">
        <div className="timeline-title-row">
          <span className="timeline-icon">⏱</span>
          <h2>Security Event Audit Log</h2>
        </div>
        <span className="timeline-count">{events.length} LOGGED EVENTS</span>
      </div>
      
      {isIdle ? (
        <div className="timeline-idle">
          <p>No audit events recorded yet. Stream is standing by.</p>
        </div>
      ) : (
        <div className="timeline-container">
          {events.map((event, index) => {
            const rawType =
              'severity' in event
                ? event.severity
                : 'type' in event
                  ? event.type
                  : 'info';

            const type =
              rawType === 'critical'
                ? 'critical'
                : rawType === 'warning'
                  ? 'warning'
                  : 'info';

            const source = 'source' in event ? event.source : undefined;
            const eventKey = ('id' in event && event.id) ? event.id : `evt-${index}`;

            return (
              <div
                key={eventKey}
                className={`timeline-item ${type}`}
              >
                <div className="timeline-marker">
                  <div className={`marker-dot ${type}`}></div>
                </div>
                <div className="timeline-content">
                  <div className="timeline-meta-row">
                    <span className="timeline-timestamp">{event.timestamp}</span>
                    {source && <span className="timeline-source">[{source.toUpperCase()}]</span>}
                  </div>
                  <div className={`timeline-message ${type}`}>
                    {event.message}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
