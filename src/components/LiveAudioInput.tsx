import React, { useEffect, useRef, useState } from 'react';
import { AudioProcessor } from '../audio/AudioProcessor';
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
  onAudioData?: (audioData: Float32Array) => void;
  onAudioChunk?: (audioChunk: Float32Array) => void;
}

export const LiveAudioInput: React.FC<LiveAudioInputProps> = ({
  isMonitoring,
  onAudioContextReady,
  onError,
  onAudioData,
  onAudioChunk
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isActive, setIsActive] = useState(false);
  const [signalLevel, setSignalLevel] = useState(0);
  const [sampleRate, setSampleRate] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);
  const onAudioDataRef = useRef<((audioData: Float32Array) => void) | null>(null);
  const onAudioChunkRef = useRef<((audioChunk: Float32Array) => void) | null>(null);
  const audioProcessorRef = useRef<AudioProcessor | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);

  // Keep the callbacks in sync to avoid closure issues
  useEffect(() => {
    onAudioDataRef.current = onAudioData || null;
  }, [onAudioData]);

  useEffect(() => {
    console.log("🔗 onAudioChunk UPDATED:", !!onAudioChunk);
    onAudioChunkRef.current = onAudioChunk || null;
  }, [onAudioChunk]);
  useEffect(() => {
    if (!isMonitoring) {
      // Stop monitoring - cleanup
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(track => track.stop());
        mediaStreamRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
      audioContextRef.current = null;
      analyserRef.current = null;
      dataArrayRef.current = null;

      if (audioProcessorRef.current) {
        audioProcessorRef.current.reset();
        audioProcessorRef.current = null;
      }
      if (scriptProcessorRef.current) {
        scriptProcessorRef.current.onaudioprocess = null;
        scriptProcessorRef.current.disconnect();
        scriptProcessorRef.current = null;
      }
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

        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const audioContext = new AudioCtx();
        audioContextRef.current = audioContext;
        setSampleRate(audioContext.sampleRate);

        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        
        const bufferLength = analyser.fftSize;
        const dataArray = new Uint8Array(bufferLength);
        dataArrayRef.current = dataArray;
        analyserRef.current = analyser;

        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        const scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        scriptProcessor.onaudioprocess = (event: AudioProcessingEvent) => {
          if (audioProcessorRef.current) {
            audioProcessorRef.current.processAudioData(event.inputBuffer.getChannelData(0));
          }
        };
        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);
        scriptProcessorRef.current = scriptProcessor;

        onAudioContextReady?.({
          audioContext,
          analyser,
          dataArray,
          mediaStream: stream
        });

        // Initialize audio processor for 16 kHz resampling and chunking
        audioProcessorRef.current = new AudioProcessor({
          inputSampleRate: audioContext.sampleRate,
          targetSampleRate: 16000,
          chunkSize: 16000, // 1 second at 16 kHz
          onChunk: (chunk) => {
            console.log("📡 AUDIO CHUNK FROM PROCESSOR:", chunk.length);

            if (onAudioChunkRef.current) {
                console.log("➡️ CALLING onAudioChunk");
                onAudioChunkRef.current(chunk);
            } else {
              console.log("❌ onAudioChunkRef is NULL");
            }
          },
        });

        // Responsive canvas sizing
        const updateCanvasSize = () => {
          if (canvasRef.current && containerRef.current) {
            canvasRef.current.width = containerRef.current.clientWidth || 600;
            canvasRef.current.height = 80;
          }
        };
        updateCanvasSize();

        // Animation loop for waveform visualization and PCM data extraction
        const draw = () => {
          if (!analyserRef.current || !dataArrayRef.current) return;

          analyserRef.current.getByteTimeDomainData(dataArrayRef.current);

          const normalizedSamples = new Float32Array(dataArrayRef.current.length);
          for (let i = 0; i < dataArrayRef.current.length; i++) {
            normalizedSamples[i] = (dataArrayRef.current[i] - 128) / 128;
          }

          if (onAudioDataRef.current) {
            onAudioDataRef.current(normalizedSamples);
          }

          // Calculate RMS from time-domain data for signal level
          let sum = 0;
          for (let i = 0; i < normalizedSamples.length; i++) {
            sum += normalizedSamples[i] * normalizedSamples[i];
          }
          const rms = Math.sqrt(sum / normalizedSamples.length);
          const levelPercent = Math.round(Math.min(100, rms * 140));
          setSignalLevel(levelPercent);

          // Draw oscilloscope waveform
          const canvas = canvasRef.current;
          if (!canvas) return;
          const ctx = canvas.getContext('2d');
          if (!ctx) return;

          const width = canvas.width;
          const height = canvas.height;

          // Clear with technical dark background
          ctx.fillStyle = '#0a0d14';
          ctx.fillRect(0, 0, width, height);

          // Draw subtle technical grid
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
          ctx.lineWidth = 1;

          // Vertical grid lines
          const gridStepX = 40;
          for (let gx = 0; gx < width; gx += gridStepX) {
            ctx.beginPath();
            ctx.moveTo(gx, 0);
            ctx.lineTo(gx, height);
            ctx.stroke();
          }

          // Horizontal grid lines
          const gridStepY = 20;
          for (let gy = 0; gy < height; gy += gridStepY) {
            ctx.beginPath();
            ctx.moveTo(0, gy);
            ctx.lineTo(width, gy);
            ctx.stroke();
          }

          // Center baseline
          ctx.strokeStyle = 'rgba(6, 182, 212, 0.25)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(0, height / 2);
          ctx.lineTo(width, height / 2);
          ctx.stroke();

          // Time-domain waveform trace
          ctx.lineWidth = 1.8;
          ctx.strokeStyle = '#06b6d4';
          ctx.shadowColor = 'rgba(6, 182, 212, 0.6)';
          ctx.shadowBlur = 6;
          ctx.beginPath();

          const sliceWidth = width / normalizedSamples.length;
          let x = 0;

          for (let i = 0; i < normalizedSamples.length; i++) {
            const v = normalizedSamples[i];
            const y = (v * (height * 0.85)) / 2 + height / 2;

            if (i === 0) {
              ctx.moveTo(x, y);
            } else {
              ctx.lineTo(x, y);
            }

            x += sliceWidth;
          }

          ctx.stroke();
          ctx.shadowBlur = 0; // reset blur

          animationFrameRef.current = requestAnimationFrame(draw);
        };

        animationFrameRef.current = requestAnimationFrame(draw);
      } catch (err) {
        const errorMessage =
          err instanceof DOMException
            ? err.name === 'NotAllowedError'
              ? 'Microphone permission denied by browser'
              : err.name === 'NotFoundError'
                ? 'No audio capture device found'
                : 'Microphone hardware error: ' + err.message
            : 'Failed to access audio hardware';
        setError(errorMessage);
        onError?.(errorMessage);
        setIsActive(false);
      }
    };

    startAudio();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [isMonitoring, onAudioContextReady, onError]);

  // LED bar representation (24 discreet segments)
  const totalLeds = 24;
  const activeLeds = Math.round((signalLevel / 100) * totalLeds);

  return (
    <div className="live-audio-input-panel">
      {/* Header */}
      <div className="audio-header-bar">
        <div className="audio-title-group">
          <span className="audio-icon-glyph">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v12a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </span>
          <h3 className="audio-title">LIVE ACOUSTIC INTAKE</h3>
        </div>

        <div className="audio-status-pill">
          <span className={`status-indicator-dot ${isActive ? 'online' : 'offline'}`}></span>
          <span className="status-indicator-label">
            {isActive ? 'MIC ACTIVE — 16KHZ RESAMPLING' : 'HARDWARE OFFLINE'}
          </span>
        </div>
      </div>

      {error ? (
        <div className="audio-error-banner">
          <span className="error-icon">⚠</span>
          <p>{error}</p>
        </div>
      ) : isActive ? (
        <div className="audio-active-body">
          {/* Oscilloscope Viewport */}
          <div className="waveform-viewport" ref={containerRef}>
            <canvas ref={canvasRef} className="waveform-canvas"></canvas>
            <div className="viewport-overlay-corner tl">CH1 • TIME-DOMAIN</div>
            <div className="viewport-overlay-corner tr">PCM STREAM</div>
          </div>

          {/* Metrics bar */}
          <div className="audio-telemetry-row">
            {/* LED Gain Meter */}
            <div className="telemetry-meter-group">
              <div className="meter-label-row">
                <span className="meter-caption">INPUT GAIN</span>
                <span className="meter-value">{signalLevel}%</span>
              </div>
              <div className="led-segment-track">
                {Array.from({ length: totalLeds }).map((_, idx) => {
                  const isLit = idx < activeLeds;
                  let colorType = 'normal';
                  if (idx >= totalLeds * 0.8) colorType = 'clip';
                  else if (idx >= totalLeds * 0.55) colorType = 'warn';

                  return (
                    <span
                      key={idx}
                      className={`led-bar-segment ${colorType} ${isLit ? 'lit' : 'dim'}`}
                    />
                  );
                })}
              </div>
            </div>

            {/* Pipeline Specs */}
            <div className="telemetry-specs">
              <div className="spec-pill">
                <span className="spec-dim">HARDWARE:</span>
                <span className="spec-val">{sampleRate} Hz</span>
              </div>
              <div className="spec-pill">
                <span className="spec-dim">DOWNSTREAM:</span>
                <span className="spec-val highlight">16 kHz / 1s Float32</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="audio-standby-state">
          <div className="standby-pulse-circle">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 1a3 3 0 0 0-3 3v12a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            </svg>
          </div>
          <div className="standby-text-block">
            <span className="standby-heading">Microphone Stream Inactive</span>
            <span className="standby-hint">Click &quot;Start Monitoring&quot; above to capture and process live microphone audio.</span>
          </div>
        </div>
      )}
    </div>
  );
};
