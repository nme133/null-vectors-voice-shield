import { TranscriptMessage } from '../data/mockData';
import './LiveTranscript.css';
import { useEffect, useRef } from 'react';

interface LiveTranscriptProps {
  messages: TranscriptMessage[];
}

export const LiveTranscript: React.FC<LiveTranscriptProps> = ({ messages }) => {
  const endRef = useRef<HTMLDivElement>(null);
  const isIdle = messages.length === 0;

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="live-transcript">
      <div className="transcript-header">
        <h2>Live Transcript</h2>
        <div className="transcript-indicator">
          <span className="pulse"></span>
          <span>Recording</span>
        </div>
      </div>
      
      <div className="transcript-container">
        {isIdle ? (
          <div className="transcript-idle">
            <p>Waiting for audio...</p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`transcript-message ${msg.speaker}`}
              >
                <div className="message-timestamp">[{msg.timestamp}]</div>
                <div className="message-speaker">
                  {msg.speaker === 'caller' ? 'Caller:' : 'You:'}
                </div>
                <div className="message-text">{msg.text}</div>
              </div>
            ))}
          </>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
};
