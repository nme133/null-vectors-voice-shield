import { useState, useEffect, useRef } from 'react';
import { Header } from '../components/Header';
import { CallStatus } from '../components/CallStatus';
import { RiskScore } from '../components/RiskScore';
import { VoiceAuthenticity } from '../components/VoiceAuthenticity';
import { ConversationAnalysis } from '../components/ConversationAnalysis';
import { LiveTranscript } from '../components/LiveTranscript';
import { RiskFactors } from '../components/RiskFactors';
import { RecommendedAction } from '../components/RecommendedAction';
import { EventTimeline } from '../components/EventTimeline';
import { SystemStatus } from '../components/SystemStatus';
import { LiveAudioInput } from '../components/LiveAudioInput';
import { getIdleDashboardState, getMockDashboardState, DashboardState } from '../data/mockData';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  // Initialize with IDLE state
  const [dashboardState, setDashboardState] = useState<DashboardState>(getIdleDashboardState());
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const durationIntervalRef = useRef<number | null>(null);
  const demoTimeoutRef = useRef<number | null>(null);

  // Handle timer increment for call duration
  useEffect(() => {
    if (!isMonitoring) {
      if (durationIntervalRef.current !== null) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }
      return;
    }

    durationIntervalRef.current = window.setInterval(() => {
      setDashboardState(prev => ({
        ...prev,
        callDuration: prev.callDuration + 1
      }));
    }, 1000);

    return () => {
      if (durationIntervalRef.current !== null) {
        clearInterval(durationIntervalRef.current);
      }
    };
  }, [isMonitoring]);

  // Cleanup demo mode timeouts
  useEffect(() => {
    return () => {
      if (demoTimeoutRef.current !== null) {
        clearTimeout(demoTimeoutRef.current);
      }
    };
  }, []);

  const handleStartMonitoring = async () => {
    setIsMonitoring(true);
    setDashboardState(prev => ({
      ...prev,
      callStatus: 'live',
      callDuration: 0,
      audioStreamActive: true,
      callerIdentity: 'Monitoring...'
    }));
  };

  const handleStopMonitoring = () => {
    setIsMonitoring(false);
    setDashboardState(prev => ({
      ...prev,
      audioStreamActive: false
    }));
  };

  const handleEndCall = () => {
    setIsMonitoring(false);
    setDashboardState(prev => ({
      ...prev,
      callStatus: 'ended',
      audioStreamActive: false
    }));
  };

  const handleReset = () => {
    setIsMonitoring(false);
    setIsDemoMode(false);
    if (demoTimeoutRef.current !== null) {
      clearTimeout(demoTimeoutRef.current);
      demoTimeoutRef.current = null;
    }
    setDashboardState(getIdleDashboardState());
  };

  const handleStartDemo = () => {
    setIsDemoMode(true);
    setIsMonitoring(false);
    setDashboardState(getMockDashboardState());
  };

  const handleStopDemo = () => {
    setIsDemoMode(false);
    if (demoTimeoutRef.current !== null) {
      clearTimeout(demoTimeoutRef.current);
      demoTimeoutRef.current = null;
    }
    setDashboardState(getIdleDashboardState());
  };

  return (
    <div className="dashboard">
      <Header connectionStatus={dashboardState.connectionStatus} />

      <main className="dashboard-main">
        <div className="dashboard-layout">
          {/* Control Bar */}
          <section className="section controls-section">
            <div className="controls-container">
              <div className="control-group">
                <button
                  className={`control-btn btn-start ${isMonitoring ? 'disabled' : ''}`}
                  onClick={handleStartMonitoring}
                  disabled={isMonitoring || isDemoMode}
                >
                  START MONITORING
                </button>
                <button
                  className={`control-btn btn-stop ${!isMonitoring ? 'disabled' : ''}`}
                  onClick={handleStopMonitoring}
                  disabled={!isMonitoring}
                >
                  STOP MONITORING
                </button>
                <button
                  className={`control-btn btn-end ${dashboardState.callStatus === 'idle' ? 'disabled' : ''}`}
                  onClick={handleEndCall}
                  disabled={dashboardState.callStatus === 'idle'}
                >
                  END CALL
                </button>
                <button
                  className="control-btn btn-reset"
                  onClick={handleReset}
                >
                  RESET
                </button>
              </div>

              <div className="control-group demo-group">
                {!isDemoMode ? (
                  <button
                    className={`control-btn btn-demo ${isMonitoring ? 'disabled' : ''}`}
                    onClick={handleStartDemo}
                    disabled={isMonitoring}
                  >
                    START DEMO
                  </button>
                ) : (
                  <button
                    className="control-btn btn-demo active"
                    onClick={handleStopDemo}
                  >
                    STOP DEMO
                  </button>
                )}
              </div>
            </div>
            {isDemoMode && <div className="demo-indicator">DEMO MODE</div>}
          </section>

          {/* Live Audio Input */}
          <section className="section section-audio">
            <LiveAudioInput isMonitoring={isMonitoring} />
          </section>

          {/* Top Section: Call Status and Risk Score */}
          <section className="section section-top">
            <div className="section-content">
              <CallStatus
                callStatus={dashboardState.callStatus}
                callDuration={dashboardState.callDuration}
                callerIdentity={dashboardState.callerIdentity}
                audioStreamActive={dashboardState.audioStreamActive}
              />
              <RiskScore score={dashboardState.riskScore} />
            </div>
          </section>

          {/* Middle Section: Voice Auth and Conversation Analysis */}
          <section className="section section-middle">
            <div className="section-content">
              <VoiceAuthenticity
                model={dashboardState.voiceAuthModel}
                score={dashboardState.voiceAuthScore}
                status={dashboardState.voiceAuthStatus}
                confidence={dashboardState.voiceAuthConfidence}
              />
              <ConversationAnalysis signals={dashboardState.detectedSignals} />
            </div>
          </section>

          {/* Recommended Action - Full Width */}
          <section className="section section-recommendation">
            <RecommendedAction
              action={dashboardState.recommendedAction}
              description={dashboardState.actionDescription}
            />
          </section>

          {/* Transcript Section */}
          <section className="section section-transcript">
            <LiveTranscript messages={dashboardState.transcript} />
          </section>

          {/* Risk Factors Section */}
          <section className="section section-risk-factors">
            <RiskFactors factors={dashboardState.riskFactors} />
          </section>

          {/* Timeline and System Status */}
          <section className="section section-bottom">
            <div className="section-content">
              <EventTimeline events={dashboardState.timeline} />
              <SystemStatus components={dashboardState.systemComponents} />
            </div>
          </section>
        </div>
      </main>

      <footer className="dashboard-footer">
        <p>VoxShield • Real-Time Voice Impersonation Detection System</p>
        <p>For demonstration and authorized security use only.</p>
      </footer>
    </div>
  );
};
