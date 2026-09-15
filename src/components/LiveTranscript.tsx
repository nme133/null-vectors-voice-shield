import React, { useEffect, useRef } from 'react';
import { TranscriptMessage } from '../data/mockData';
import './LiveTranscript.css';

interface LiveTranscriptProps {
  messages: TranscriptMessage[];
  variant?: 'compact' | 'full';
  onNavigateToTranscript?: () => void;
}

export const LiveTranscript: React.FC<LiveTranscriptProps> = ({
  messages,
  variant = 'compact',
  onNavigateToTranscript
}) => {
  const endRef = useRef<HTMLDivElement>(null);
  const isIdle = messages.length === 0;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // If compact, only take the last 3 messages so it remains secondary to risk score
  const displayMessages = variant === 'compact' ? messages.slice(-3) : messages;

  return (
    <div className={`live-transcript-panel ${variant}`}>
      <div className="transcript-header-bar">
        <div className="transcript-title-group">
          <span className="transcript-live-dot"></span>
          <h3 className="transcript-title">LIVE SPEECH STREAM (WHISPER ASR)</h3>
        </div>

        <div className="transcript-actions">
          {variant === 'compact' && onNavigateToTranscript && (
            <button
              className="view-full-transcript-btn"
              onClick={onNavigateToTranscript}
            >
              FULL TRANSCRIPT &rarr;
            </button>
          )}
        </div>
      </div>

      <div className="transcript-body">
        {isIdle ? (
          <div className="transcript-idle-state">
            <span className="idle-wave-icon">💬</span>
            <p className="idle-text">
              {variant === 'compact'
                ? 'Speech stream will transcribe live incoming voice in real-time...'
                : 'No conversational data recorded yet. Initiate call monitoring or launch Demo Mode.'}
            </p>
          </div>
        ) : (
          <div className="transcript-messages-stream">
            {displayMessages.map((msg) => (
              <div key={msg.id} className={`transcript-bubble ${msg.speaker}`}>
                <div className="bubble-meta">
                  <span className={`speaker-tag ${msg.speaker}`}>
                    {msg.speaker === 'caller' ? 'CALLER' : 'YOU'}
                  </span>
                  <span className="msg-time">{msg.timestamp}</span>
                </div>
                <div className="bubble-text">&ldquo;{msg.text}&rdquo;</div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>
    </div>
  );
};
