import React, { useEffect, useRef, useState } from 'react';
import './LiveAudioInput.css';

export interface AudioContextState {
  audioContext: AudioContext | null;
  analyser: AnalyserNode | null;
  dataArray: Uint8Array | null;
  mediaStream: MediaStream | null;
}

export interface LiveAudioInputProps {
  isMonitoring: boolean;
  onAudioContextReady?: (state: AudioContextState) => void;
  onError?: (error: string) => void;
}

export const LiveAudioInput: React.FC<LiveAudioInputProps> = ({
  isMonitoring,
  onAudioContextReady,
  onError
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isActive, setIsActive] = useState(false);
  const [signalLevel, setSignalLevel] = useState(0);
  const [sampleRate, setSampleRate] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);

  useEffect(() => {
    if (!isMonitoring) {
      // Stop monitoring
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(track => track.stop());
        mediaStreamRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      analyserRef.current = null;
      dataArrayRef.current = null;
      setIsActive(false);
      setSignalLevel(0);
      setError(null);
      return;
    }

    // Start monitoring
    const startAudio = async () => {
      try {
        setError(null);
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false
          }
        });

        mediaStreamRef.current = stream;
        setIsActive(true);

        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioContextRef.current = audioContext;
        setSampleRate(audioContext.sampleRate);

        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        dataArrayRef.current = dataArray;
        analyserRef.current = analyser;

        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        onAudioContextReady?.({
          audioContext,
          analyser,
          dataArray,
          mediaStream: stream
        });

        // Animation loop for waveform
        const draw = () => {
          if (!analyserRef.current || !dataArrayRef.current) return;

          analyserRef.current.getByteFrequencyData(dataArrayRef.current);

          // Calculate RMS from frequency data
          let sum = 0;
          for (let i = 0; i < dataArrayRef.current.length; i++) {
            const normalized = dataArrayRef.current[i] / 255;
            sum += normalized * normalized;
          }
          const rms = Math.sqrt(sum / dataArrayRef.current.length);
          const dbLevel = Math.max(-60, 20 * Math.log10(rms + 0.0001));
          const displayLevel = Math.round(((dbLevel + 60) / 60) * 100);
          setSignalLevel(Math.max(0, Math.min(100, displayLevel)));

          // Draw waveform
          const canvas = canvasRef.current;
          if (!canvas) return;

          const ctx = canvas.getContext('2d');
          if (!ctx) return;

          const width = canvas.width;
          const height = canvas.height;

          ctx.fillStyle = 'rgba(15, 15, 15, 1)';
          ctx.fillRect(0, 0, width, height);

          // Draw center line
          ctx.strokeStyle = 'rgba(59, 130, 246, 0.2)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(0, height / 2);
          ctx.lineTo(width, height / 2);
          ctx.stroke();

          // Draw waveform
          ctx.strokeStyle = 'rgba(59, 130, 246, 0.8)';
          ctx.lineWidth = 2;
          ctx.beginPath();

          const sliceWidth = width / dataArrayRef.current.length;
          let x = 0;

          for (let i = 0; i < dataArrayRef.current.length; i++) {
            const v = dataArrayRef.current[i] / 128.0;
            const y = (v * height) / 2;

            if (i === 0) {
              ctx.moveTo(x, y);
            } else {
              ctx.lineTo(x, y);
            }

            x += sliceWidth;
          }

          ctx.lineTo(width, height / 2);
          ctx.stroke();

          animationFrameRef.current = requestAnimationFrame(draw);
        };

        animationFrameRef.current = requestAnimationFrame(draw);
      } catch (err) {
        const errorMessage =
          err instanceof DOMException
            ? err.name === 'NotAllowedError'
              ? 'Microphone access denied'
              : err.name === 'NotFoundError'
                ? 'No microphone detected'
                : 'Microphone error: ' + err.message
            : 'Failed to access microphone';
        setError(errorMessage);
        onError?.(errorMessage);
        setIsActive(false);
      }
    };

    startAudio();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isMonitoring, onAudioContextReady, onError]);

  const getBarFill = (percentage: number) => {
    const filled = Math.round((percentage / 100) * 10);
    return '█'.repeat(filled) + '░'.repeat(10 - filled);
  };

  return (
    <div className="live-audio-input">
      <div className="audio-header">
        <h3>LIVE AUDIO INPUT</h3>
        <div className={`audio-status ${isActive ? 'active' : 'offline'}`}>
          <span className={`status-indicator ${isActive ? 'active' : 'offline'}`}></span>
          {isActive ? 'MICROPHONE ACTIVE' : 'MICROPHONE OFFLINE'}
        </div>
      </div>

      {error ? (
        <div className="audio-error">
          <p>{error}</p>
        </div>
      ) : isActive ? (
        <>
          <div className="waveform-container">
            <canvas ref={canvasRef} width={600} height={100} className="waveform-canvas"></canvas>
          </div>

          <div className="signal-info">
            <div className="signal-level-section">
              <label>INPUT LEVEL</label>
              <div className="level-bars">{getBarFill(signalLevel)}</div>
              <span className="level-db">{Math.round(signalLevel / 5 - 12)} dB</span>
            </div>

            <div className="audio-specs">
              <div className="spec-item">
                <span className="spec-label">Sample Rate</span>
                <span className="spec-value">{sampleRate} Hz</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">Channel</span>
                <span className="spec-value">Mono</span>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="audio-waiting">
          <p>Waiting for microphone...</p>
        </div>
      )}
    </div>
  );
};
