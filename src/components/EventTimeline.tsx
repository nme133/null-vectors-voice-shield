import { TimelineEvent } from '../data/mockData';
import './EventTimeline.css';

interface EventTimelineProps {
  events: TimelineEvent[];
}

export const EventTimeline: React.FC<EventTimelineProps> = ({ events }) => {
  const isIdle = events.length === 0;

  return (
    <div className="event-timeline">
      <div className="timeline-header">
        <h2>Event Timeline</h2>
      </div>
      
      {isIdle ? (
        <div className="timeline-idle">
          <p>Waiting for live analysis...</p>
        </div>
      ) : (
        <div className="timeline-container">
          {events.map((event, index) => (
            <div
              key={index}
              className={`timeline-item ${event.type}`}
            >
              <div className="timeline-marker">
                <div className={`marker-dot ${event.type}`}></div>
              </div>
              <div className="timeline-content">
                <div className="timeline-timestamp">{event.timestamp}</div>
                <div className={`timeline-message ${event.type}`}>
                  {event.message}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
