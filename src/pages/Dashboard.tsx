import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header, NavTab } from '../components/Header';
import { CallStatus } from '../components/CallStatus';
import { HeroRiskGauge } from '../components/HeroRiskGauge';
import { RiskEngineFeed } from '../components/RiskEngineFeed';
import { LiveAudioInput } from '../components/LiveAudioInput';
import { LiveTranscript } from '../components/LiveTranscript';
import { AudioFileUpload } from '../components/AudioFileUpload';
import { VoiceAuthenticity } from '../components/VoiceAuthenticity';
import { VoiceAuthenticityMini } from '../components/VoiceAuthenticityMini';
import { ConversationAnalysis } from '../components/ConversationAnalysis';
import { RiskFactors } from '../components/RiskFactors';
import { EventTimeline } from '../components/EventTimeline';
import { SystemStatus } from '../components/SystemStatus';
import {
  getIdleDashboardState,
  DEMO_PROGRESSION,
  DashboardState,
  RiskFactor,
  RiskLevel,
  getRiskLevel
} from '../data/mockData';
import {
  BackendStreamMessage
} from '../backend/streamTypes';
import { useBackendStream } from '../backend/useBackendStream';
import './Dashboard.css';

const formatTimestamp = (): string => {
  const now = new Date();
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${minutes}:${seconds}`;
};

export const Dashboard: React.FC = () => {
  // Primary Dashboard State - Normal startup is strictly IDLE
  const [dashboardState, setDashboardState] = useState<DashboardState>(getIdleDashboardState());
  const [activeTab, setActiveTab] = useState<NavTab>('overview');
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [demoStepIndex, setDemoStepIndex] = useState(0);
  // Bumped on RESET to remount the upload panel (clears its file/status/result).
  const [uploadSessionId, setUploadSessionId] = useState(0);

  // Settings state
  const [demoSpeed, setDemoSpeed] = useState<'normal' | 'fast'>('normal');
  const [spoofSensitivity, setSpoofSensitivity] = useState(70);
  const [urgencySensitivity, setUrgencySensitivity] = useState(65);
  const [transcriptionLanguage, setTranscriptionLanguage] = useState<string>('auto');

  const durationIntervalRef = useRef<number | null>(null);
  const demoIntervalRef = useRef<number | null>(null);

  // Backend WebSocket integration state
  const [backendError, setBackendError] = useState<string | null>(null);
  const seenReasonsRef = useRef<Set<string>>(new Set());
  // True once the backend has delivered a real conversation_analysis message.
  // Drives the Analysis tab: the "AWAITING SPEECH TRANSCRIPT" placeholder only
  // shows before the first analysis arrives, never while weak-but-real signals
  // are being rendered.
  const [hasConversationAnalysis, setHasConversationAnalysis] = useState(false);

  // Map actual backend stream messages into dashboard state.
  const handleBackendMessage = useCallback((msg: BackendStreamMessage) => {
    switch (msg.type) {
      case 'connected': {
        setDashboardState((prev) => ({
          ...prev,
          connectionStatus: 'online',
          systemComponents: {
            voiceAnalysis: msg.spectra_loaded ? 'active' : 'inactive',
            speechTranscription: 'active',
            conversationAnalysis: 'active',
            riskEngine: 'active'
          }
        }));
        break;
      }
      case 'voice_analysis': {
        setDashboardState((prev) => ({
          ...prev,
          voice: {
            score: msg.score,
            isSpoof: msg.is_spoof,
            confidence: msg.confidence,
            model: msg.model || prev.voice.model,
            status: msg.status ?? prev.voice.status
          }
        }));
        break;
      }
      case 'transcript': {
        setDashboardState((prev) => ({
          ...prev,
          transcript: [
            ...prev.transcript,
            {
              id: msg.id,
              timestamp: msg.timestamp,
              speaker: msg.speaker,
              text: msg.text
            }
          ]
        }));
        break;
      }
      case 'conversation_analysis': {
        setHasConversationAnalysis(true);
        setDashboardState((prev) => ({
          ...prev,
          conversation: {
            urgency: msg.urgency,
            authorityImpersonation: msg.authority_impersonation,
            financialRequest: msg.financial_request,
            credentialRequest: msg.credential_request,
            otpRequest: msg.otp_request,
            threat: msg.threat,
            secrecy: msg.secrecy,
            persuasion: msg.persuasion,
            repeatedConfirmation: msg.repeated_confirmation,
            confidence: msg.confidence,
            reasons: msg.reasons
          }
        }));
        break;
      }
      case 'risk_update': {
        setDashboardState((prev) => {
          const newEvents = [...prev.events];
          const seen = seenReasonsRef.current;
          msg.reasons.forEach((reason) => {
            if (!seen.has(reason)) {
              seen.add(reason);
              newEvents.push({
                id: `reason-${Date.now()}-${newEvents.length}`,
                timestamp: formatTimestamp(),
                message: reason,
                severity: 'warning' as const,
                source: 'engine' as const
              });
            }
          });

          const riskFactors: RiskFactor[] = msg.reasons.map((reason, idx) => ({
            id: `reason-${Date.now()}-${idx}`,
            name: reason,
            status: 'detected' as const,
            description: 'Reported by the real-time risk engine from live acoustic and conversational signals.'
          }));

          return {
            ...prev,
            riskScore: msg.risk_score,
            riskLevel: msg.risk_level as RiskLevel,
            recommendation: msg.recommendation
              ? {
                  action: msg.recommendation,
                  description: 'Recommended by the real-time risk engine based on live acoustic and conversational signals.'
                }
              : prev.recommendation,
            events: newEvents,
            riskFactors
          };
        });
        break;
      }
      case 'event': {
        setDashboardState((prev) => ({
          ...prev,
          events: [
            ...prev.events,
            {
              id: msg.id,
              timestamp: msg.timestamp,
              message: msg.message,
              severity: msg.severity,
              source: msg.source
            }
          ]
        }));
        break;
      }
      case 'error': {
        setDashboardState((prev) => ({
          ...prev,
          events: [
            ...prev.events,
            {
              id: `err-${Date.now()}`,
              timestamp: formatTimestamp(),
              message: msg.message,
              severity: 'critical' as const,
              source: 'engine' as const
            }
          ]
        }));
        break;
      }
      default:
        break;
    }
  }, []);

  const { status, connect, disconnect, sendAudio, sendControl } = useBackendStream({
    onStatusChange: (nextStatus, info) => {
      if (nextStatus === 'connecting') {
        setBackendError(null);
        setDashboardState((prev) => ({ ...prev, connectionStatus: 'offline' }));
      } else if (nextStatus === 'open') {
        setBackendError(null);
        setDashboardState((prev) => ({ ...prev, connectionStatus: 'online' }));
      } else if (nextStatus === 'error') {
        setBackendError(info?.error ?? 'Backend connection failed');
        setDashboardState((prev) => ({ ...prev, connectionStatus: 'offline' }));
      } else if (nextStatus === 'closed') {
        setBackendError(null);
      }
    },
    onMessage: handleBackendMessage
  });

  // Open stream when monitoring starts; close it when monitoring stops.
  useEffect(() => {
    if (isDemoMode) return;
    if (isMonitoring) {
      seenReasonsRef.current.clear();
      connect();
    } else {
      sendControl('end_session');
      disconnect();
    }
  }, [isMonitoring, isDemoMode, connect, disconnect, sendControl]);

  // Start a fresh session on the backend once the socket is open.
  useEffect(() => {
    if (status === 'open' && isMonitoring) {
      sendControl('start_session');
      // Re-apply the selected language — a fresh session resets the backend value.
      if (transcriptionLanguage && transcriptionLanguage !== 'auto') {
        sendControl('set_language', { language: transcriptionLanguage });
      }
    }
  }, [status, isMonitoring, sendControl, transcriptionLanguage]);

  // Push the transcription language to the backend whenever it changes.
  const handleLanguageChange = useCallback(
    (code: string) => {
      setTranscriptionLanguage(code);
      sendControl('set_language', { language: code });
    },
    [sendControl]
  );

  // Forward 16 kHz Float32 chunks from the audio pipeline to the backend.
  const handleAudioChunk = useCallback(
    (chunk: Float32Array) => {
      sendAudio(chunk);
    },
    [sendAudio]
  );

  // Call Duration increment for live monitoring
  useEffect(() => {
    if (!isMonitoring) {
      if (durationIntervalRef.current !== null) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }
      return;
    }

    durationIntervalRef.current = window.setInterval(() => {
      setDashboardState((prev) => ({
        ...prev,
        callDuration: prev.callDuration + 1
      }));
    }, 1000);

    return () => {
      if (durationIntervalRef.current !== null) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }
    };
  }, [isMonitoring]);

  // Demo Mode Progression Engine (for SIH Presentation)
  useEffect(() => {
    if (!isDemoMode) {
      if (demoIntervalRef.current !== null) {
        clearInterval(demoIntervalRef.current);
        demoIntervalRef.current = null;
      }
      return;
    }

    const intervalMs = demoSpeed === 'fast' ? 2200 : 3600;

    demoIntervalRef.current = window.setInterval(() => {
      setDemoStepIndex((prevIndex) => {
        const nextIndex = prevIndex + 1;
        if (nextIndex >= DEMO_PROGRESSION.length) {
          // Reached end of demo sequence - keep final critical state
          if (demoIntervalRef.current !== null) {
            clearInterval(demoIntervalRef.current);
            demoIntervalRef.current = null;
          }
          return prevIndex;
        }

        const step = DEMO_PROGRESSION[nextIndex];

        setDashboardState((prev) => {
          const newTranscript = step.transcriptNewMessage
            ? [...prev.transcript, step.transcriptNewMessage]
            : prev.transcript;

          const newEvents = step.eventsNewEvent
            ? [...prev.events, step.eventsNewEvent]
            : prev.events;

          return {
            ...prev,
            callStatus: 'live',
            callerIdentity: step.callerIdentity,
            riskScore: step.riskScore,
            riskLevel: getRiskLevel(step.riskScore),
            voice: step.voice,
            conversation: step.conversation,
            transcript: newTranscript,
            events: newEvents,
            recommendation: step.recommendation || prev.recommendation,
            riskFactors: step.riskFactors.length ? step.riskFactors : prev.riskFactors,
            systemComponents: {
              voiceAnalysis: 'active',
              speechTranscription: 'active',
              conversationAnalysis: 'active',
              riskEngine: 'active'
            }
          };
        });

        return nextIndex;
      });
    }, intervalMs);

    return () => {
      if (demoIntervalRef.current !== null) {
        clearInterval(demoIntervalRef.current);
        demoIntervalRef.current = null;
      }
    };
  }, [isDemoMode, demoSpeed]);

  // Call Controls: Start Monitoring (Real Mic)
  const handleStartMonitoring = () => {
    if (isDemoMode) handleStopDemo();
    setHasConversationAnalysis(false);
    setIsMonitoring(true);
    setDashboardState((prev) => ({
      ...prev,
      connectionStatus: 'offline',
      callStatus: 'live',
      callDuration: 0,
      audioStreamActive: true,
      callerIdentity: 'Active Mic Session',
      // Real monitoring starts with clean baseline until backend pushes data
      riskScore: prev.riskScore || 0,
      riskLevel: getRiskLevel(prev.riskScore || 0),
      systemComponents: {
        voiceAnalysis: 'active',
        speechTranscription: 'active',
        conversationAnalysis: 'active',
        riskEngine: 'active'
      }
    }));
  };

  // Stop Monitoring
  const handleStopMonitoring = () => {
    setIsMonitoring(false);
    setDashboardState((prev) => ({
      ...prev,
      audioStreamActive: false
    }));
  };

  // End Call
  const handleEndCall = () => {
    setIsMonitoring(false);
    if (isDemoMode) {
      if (demoIntervalRef.current !== null) {
        clearInterval(demoIntervalRef.current);
        demoIntervalRef.current = null;
      }
    }
    setDashboardState((prev) => ({
      ...prev,
      callStatus: 'ended',
      audioStreamActive: false
    }));
  };

  // Pure Reset
  const handleReset = () => {
    setIsMonitoring(false);
    setIsDemoMode(false);
    setDemoStepIndex(0);
    setHasConversationAnalysis(false);
    setUploadSessionId((id) => id + 1);
    if (demoIntervalRef.current !== null) {
      clearInterval(demoIntervalRef.current);
      demoIntervalRef.current = null;
    }
    if (durationIntervalRef.current !== null) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
    setDashboardState(getIdleDashboardState());
  };

  // Launch Demo Mode (SIH Presentation)
  const handleStartDemo = () => {
    handleReset();
    setIsDemoMode(true);
    setDemoStepIndex(0);
    setHasConversationAnalysis(true);

    const initialStep = DEMO_PROGRESSION[0];
    setDashboardState({
      connectionStatus: 'online',
      callStatus: 'live',
      callDuration: 0,
      callerIdentity: initialStep.callerIdentity,
      audioStreamActive: true,
      riskScore: initialStep.riskScore,
      riskLevel: getRiskLevel(initialStep.riskScore),
      voice: initialStep.voice,
      conversation: initialStep.conversation,
      transcript: initialStep.transcriptNewMessage ? [initialStep.transcriptNewMessage] : [],
      events: initialStep.eventsNewEvent ? [initialStep.eventsNewEvent] : [],
      recommendation: initialStep.recommendation || { action: '', description: '' },
      riskFactors: initialStep.riskFactors,
      systemComponents: {
        voiceAnalysis: 'active',
        speechTranscription: 'active',
        conversationAnalysis: 'active',
        riskEngine: 'active'
      }
    });
  };

  // Stop Demo Mode
  const handleStopDemo = () => {
    setIsDemoMode(false);
    if (demoIntervalRef.current !== null) {
      clearInterval(demoIntervalRef.current);
      demoIntervalRef.current = null;
    }
  };

  return (
    <div className="command-center-app">
      {/* Top Header with Navigation */}
      <Header
        connectionStatus={dashboardState.connectionStatus}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isMonitoring={isMonitoring}
        isDemoMode={isDemoMode}
      />

      {/* Main Container */}
      <main className="command-center-main">
        {/* Global Control Strip */}
        <section className="control-strip-panel">
          <div className="controls-group left-actions">
            <button
              className={`action-btn btn-start ${isMonitoring ? 'disabled' : ''}`}
              onClick={handleStartMonitoring}
              disabled={isMonitoring || isDemoMode}
              title="Activate microphone hardware and start audio intake"
            >
              <span className="btn-icon">▶</span>
              START MONITORING
            </button>

            <button
              className={`action-btn btn-stop ${!isMonitoring ? 'disabled' : ''}`}
              onClick={handleStopMonitoring}
              disabled={!isMonitoring}
              title="Pause audio intake"
            >
              <span className="btn-icon">⏸</span>
              PAUSE
            </button>

            <button
              className={`action-btn btn-end ${dashboardState.callStatus === 'idle' ? 'disabled' : ''}`}
              onClick={handleEndCall}
              disabled={dashboardState.callStatus === 'idle'}
              title="Terminate call session"
            >
              <span className="btn-icon">⏹</span>
              END CALL
            </button>

            <button
              className="action-btn btn-reset"
              onClick={handleReset}
              title="Reset system to clean idle state"
            >
              <span className="btn-icon">↺</span>
              RESET
            </button>
          </div>

          <div className="controls-group right-actions">
            {!isDemoMode ? (
              <button
                className={`action-btn btn-demo ${isMonitoring ? 'disabled' : ''}`}
                onClick={handleStartDemo}
                disabled={isMonitoring}
                title="Simulate realistic bank impersonation attack for SIH presentation"
              >
                <span className="demo-play-icon">⚡</span>
                RUN DEMO SIMULATION
              </button>
            ) : (
              <div className="demo-active-cluster">
                <span className="demo-step-badge">
                  STAGE {demoStepIndex + 1}/{DEMO_PROGRESSION.length}
                </span>
                <button
                  className="action-btn btn-demo active"
                  onClick={handleStopDemo}
                  title="Halt active demo presentation"
                >
                  HALT DEMO
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Backend connection state surface */}
        {(status === 'error' || status === 'connecting') && (
          <section className={`backend-connection-banner ${status}`} role="status">
            <span className="backend-conn-icon">
              {status === 'error' ? '⚠' : '⟳'}
            </span>
            <span className="backend-conn-text">
              {status === 'error'
                ? `BACKEND CONNECTION FAILED${backendError ? ` — ${backendError}` : ''}`
                : 'CONNECTING TO BACKEND STREAM...'}
            </span>
            {status === 'error' && (
              <span className="backend-conn-hint">
                Ensure the backend is running at ws://localhost:8000/api/v1/stream, then press RESET and START MONITORING again.
              </span>
            )}
          </section>
        )}

        {/* View Router */}
        {activeTab === 'overview' && (
          <div className="overview-two-column-layout">
            {/* LEFT / CENTER: Call Monitoring & Audio Experience */}
            <div className="call-monitoring-column">
              {/* Call Status Bar */}
              <CallStatus
                callStatus={dashboardState.callStatus}
                callDuration={dashboardState.callDuration}
                callerIdentity={dashboardState.callerIdentity}
                audioStreamActive={dashboardState.audioStreamActive}
              />

              {/* Hero Circular Risk Gauge (Centerpiece) */}
              <div className="hero-gauge-card">
                <div className="card-header-subtle">
                  <span className="card-eyebrow">PRIMARY THREAT ASSESSMENT</span>
                  <span className="card-hint">Spectra-AASIST3 + GPT-OSS Risk Fusion</span>
                </div>
                <div className="hero-gauge-body">
                  <VoiceAuthenticityMini
                    score={dashboardState.voice.score}
                    isSpoof={dashboardState.voice.isSpoof}
                    status={dashboardState.voice.status}
                  />
                  <HeroRiskGauge
                    score={dashboardState.riskScore}
                    level={dashboardState.riskLevel}
                    isActive={dashboardState.callStatus !== 'idle'}
                  />
                </div>
              </div>

              {/* Upload Audio — offline file analysis through the REAL models */}
              <AudioFileUpload
                key={uploadSessionId}
                language={transcriptionLanguage}
                disabled={isMonitoring || isDemoMode}
              />

              {/* Live Audio Input (Real Mic Oscilloscope) */}
              <LiveAudioInput
                isMonitoring={isMonitoring}
                onAudioChunk={handleAudioChunk}
              />

              {/* Compact Live Transcript Stream */}
              <LiveTranscript
                messages={dashboardState.transcript}
                variant="compact"
                onNavigateToTranscript={() => setActiveTab('transcript')}
              />
            </div>

            {/* RIGHT: Live Risk Engine Security Feed */}
            <div className="risk-engine-column">
              <RiskEngineFeed
                events={dashboardState.events}
                recommendation={dashboardState.recommendation}
                isActive={dashboardState.callStatus !== 'idle'}
              />
            </div>
          </div>
        )}

        {/* TAB 2: Detailed Analysis */}
        {activeTab === 'analysis' && (
          <div className="tab-pane-container analysis-tab-layout">
            <div className="analysis-grid-two-col">
              <VoiceAuthenticity
                model={dashboardState.voice.model}
                score={dashboardState.voice.score}
                confidence={dashboardState.voice.confidence}
                isSpoof={dashboardState.voice.isSpoof}
                status={dashboardState.voice.status}
              />
              <ConversationAnalysis
                signals={dashboardState.conversation}
                reasons={dashboardState.conversation.reasons}
                hasAnalysis={hasConversationAnalysis}
                recommendation={dashboardState.recommendation?.action}
              />
            </div>

            <div className="analysis-full-row">
              <RiskFactors factors={dashboardState.riskFactors} />
            </div>
          </div>
        )}

        {/* TAB 3: Full Transcript */}
        {activeTab === 'transcript' && (
          <div className="tab-pane-container transcript-tab-layout">
            <div className="tab-pane-header">
              <div>
                <h2>Full Conversational Transcript</h2>
                <p className="tab-subtitle">Real-time Whisper ASR speech-to-text logging & speaker diarization</p>
              </div>
              <div className="transcript-stats-tag">
                {dashboardState.transcript.length} UTTERANCES LOGGED
              </div>
            </div>
            <LiveTranscript messages={dashboardState.transcript} variant="full" />
          </div>
        )}

        {/* TAB 4: Events Timeline */}
        {activeTab === 'events' && (
          <div className="tab-pane-container events-tab-layout">
            <div className="tab-pane-header">
              <div>
                <h2>Security Event Timeline & Audit Log</h2>
                <p className="tab-subtitle">Chronological record of multi-vector acoustic and NLP risk escalations</p>
              </div>
              <div className="transcript-stats-tag">
                {dashboardState.events.length} THREAT EVENTS
              </div>
            </div>
            <EventTimeline events={dashboardState.events} />
          </div>
        )}

        {/* TAB 5: System Health */}
        {activeTab === 'system' && (
          <div className="tab-pane-container system-tab-layout">
            <div className="system-grid-two-col">
              <SystemStatus components={dashboardState.systemComponents} />

              <div className="system-specs-card">
                <div className="specs-card-header">
                  <h3>Audio & Pipeline Specifications</h3>
                  <span className="specs-pill">V1.0.4 PRODUCTION</span>
                </div>
                <div className="specs-table">
                  <div className="specs-row">
                    <span className="specs-key">Audio Pipeline</span>
                    <span className="specs-val">Web Audio API Float32 PCM</span>
                  </div>
                  <div className="specs-row">
                    <span className="specs-key">Acoustic Resampling</span>
                    <span className="specs-val highlight">16,000 Hz Mono (Linear Interpolation)</span>
                  </div>
                  <div className="specs-row">
                    <span className="specs-key">Audio Chunk Size</span>
                    <span className="specs-val">16,000 samples (1.0 sec window)</span>
                  </div>
                  <div className="specs-row">
                    <span className="specs-key">Deepfake Model</span>
                    <span className="specs-val">Spectra-AASIST3 (Phase/Harmonic CNN)</span>
                  </div>
                  <div className="specs-row">
                    <span className="specs-key">ASR Engine</span>
                    <span className="specs-val">Whisper Base (Streaming VAD)</span>
                  </div>
                  <div className="specs-row">
                    <span className="specs-key">NLP Threat Engine</span>
                    <span className="specs-val">GPT-OSS Intent Classifier</span>
                  </div>
                  <div className="specs-row">
                    <span className="specs-key">WebSocket Endpoint</span>
                    <span className="specs-val mono">ws://localhost:8000/api/v1/stream</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 6: Settings */}
        {activeTab === 'settings' && (
          <div className="tab-pane-container settings-tab-layout">
            <div className="settings-card">
              <div className="tab-pane-header">
                <div>
                  <h2>Command Center Settings</h2>
                  <p className="tab-subtitle">Adjust detection thresholds and simulation parameters</p>
                </div>
              </div>

              <div className="settings-controls-list">
                <div className="setting-item">
                  <div className="setting-info">
                    <label className="setting-title">Acoustic Spoof Detection Sensitivity</label>
                    <p className="setting-desc">Spectra-AASIST3 threshold for flagging synthetic vocoder artifacts.</p>
                  </div>
                  <div className="setting-slider-group">
                    <input
                      type="range"
                      min="30"
                      max="95"
                      value={spoofSensitivity}
                      onChange={(e) => setSpoofSensitivity(Number(e.target.value))}
                    />
                    <span className="setting-val-display">{spoofSensitivity}%</span>
                  </div>
                </div>

                <div className="setting-item">
                  <div className="setting-info">
                    <label className="setting-title">Conversational Urgency Trigger Level</label>
                    <p className="setting-desc">GPT-OSS NLP sensitivity to high-pressure language cues.</p>
                  </div>
                  <div className="setting-slider-group">
                    <input
                      type="range"
                      min="30"
                      max="95"
                      value={urgencySensitivity}
                      onChange={(e) => setUrgencySensitivity(Number(e.target.value))}
                    />
                    <span className="setting-val-display">{urgencySensitivity}%</span>
                  </div>
                </div>

                <div className="setting-item">
                  <div className="setting-info">
                    <label className="setting-title">Transcription Language</label>
                    <p className="setting-desc">
                      Language hint for Groq Whisper. Auto Detect lets Whisper decide;
                      picking a language (e.g. Hindi) forces the exact Whisper ISO code so
                      transcripts stop falling back to English.
                    </p>
                  </div>
                  <div className="setting-toggle-group">
                    <select
                      className="language-select"
                      value={transcriptionLanguage}
                      onChange={(e) => handleLanguageChange(e.target.value)}
                      aria-label="Transcription language"
                    >
                      <option value="auto">AUTO DETECT</option>
                      <option value="en">ENGLISH</option>
                      <option value="hi">HINDI</option>
                      <option value="bn">BENGALI</option>
                      <option value="ta">TAMIL</option>
                      <option value="te">TELUGU</option>
                      <option value="mr">MARATHI</option>
                      <option value="gu">GUJARATI</option>
                      <option value="pa">PUNJABI</option>
                      <option value="ur">URDU</option>
                    </select>
                    <span className="setting-val-display">
                      {transcriptionLanguage === 'auto'
                        ? 'AUTO DETECT'
                        : transcriptionLanguage.toUpperCase()}
                    </span>
                  </div>
                </div>

                <div className="setting-item">
                  <div className="setting-info">
                    <label className="setting-title">SIH Demo Presentation Speed</label>
                    <p className="setting-desc">Playback speed for the simulated scam escalation timeline.</p>
                  </div>
                  <div className="setting-toggle-group">
                    <button
                      className={`speed-toggle-btn ${demoSpeed === 'normal' ? 'active' : ''}`}
                      onClick={() => setDemoSpeed('normal')}
                    >
                      STANDARD (3.6s)
                    </button>
                    <button
                      className={`speed-toggle-btn ${demoSpeed === 'fast' ? 'active' : ''}`}
                      onClick={() => setDemoSpeed('fast')}
                    >
                      FAST (2.2s)
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Command Center Footer */}
      <footer className="command-center-footer">
        <div className="footer-inner">
          <span className="footer-copyright">
            NULL VECTORS // VOICE SHIELD &bull; SIH 2026 CYBER DEFENSE INITIATIVE
          </span>
          <span className="footer-security-notice">
            AUTHORIZED REAL-TIME ACOUSTIC &amp; SOCIAL ENGINEERING MONITORING
          </span>
        </div>
      </footer>
    </div>
  );
};
