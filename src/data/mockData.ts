/**
 * Data contracts and demo state definitions for Null Vectors — Voice Shield.
 * 
 * Future WebSocket payload shape matches BackendPayload:
 * {
 *   riskScore: number,
 *   riskLevel: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
 *   voice: { score: number, isSpoof: boolean, confidence: string, model: string },
 *   conversation: { urgency: number, authorityImpersonation: number, financialRequest: number, credentialRequest: number, threat: number },
 *   transcript: TranscriptMessage[],
 *   events: RiskFeedEvent[],
 *   recommendation: { action: string, description: string }
 * }
 */

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface TranscriptMessage {
  id: string;
  timestamp: string;
  speaker: 'caller' | 'user';
  text: string;
}

export interface RiskFeedEvent {
  id: string;
  timestamp: string;
  message: string;
  severity: 'info' | 'warning' | 'critical' | 'success';
  source?: 'audio' | 'voice' | 'nlp' | 'engine';
}

export interface RiskFactor {
  id: string;
  name: string;
  status: 'detected' | 'suspected' | 'clear';
  description: string;
}

export interface VoiceAnalysisData {
  score: number; // 0-100
  isSpoof: boolean;
  confidence: string;
  model: string;
  status?: 'spoof' | 'suspicious' | 'bona_fide' | 'insufficient_speech';
}

export interface ConversationAnalysisData {
  urgency: number; // 0-100 or 0-1
  authorityImpersonation: number;
  financialRequest: number;
  credentialRequest: number;
  otpRequest?: number;
  threat: number;
  secrecy?: number;
  persuasion?: number;
  repeatedConfirmation?: number;
  confidence?: number;
  reasons?: string[];
}

export interface BackendPayload {
  riskScore: number;
  riskLevel: RiskLevel;
  voice: VoiceAnalysisData;
  conversation: ConversationAnalysisData;
  transcript: TranscriptMessage[];
  events: RiskFeedEvent[];
  recommendation: {
    action: string;
    description: string;
  };
}

export interface DashboardState {
  // Connection & Active View
  connectionStatus: 'online' | 'offline';
  
  // Call Status
  callStatus: 'live' | 'ended' | 'idle';
  callDuration: number; // seconds
  callerIdentity: string;
  audioStreamActive: boolean;
  
  // Core Threat Score
  riskScore: number; // 0-100
  riskLevel: RiskLevel;
  
  // Model Data
  voice: VoiceAnalysisData;
  conversation: ConversationAnalysisData;
  
  // Feed & Recommendation
  transcript: TranscriptMessage[];
  events: RiskFeedEvent[];
  recommendation: {
    action: string;
    description: string;
  };
  
  // Risk Factors breakdown (for Analysis tab)
  riskFactors: RiskFactor[];
  
  // System Health
  systemComponents: {
    voiceAnalysis: 'active' | 'inactive';
    speechTranscription: 'active' | 'inactive';
    conversationAnalysis: 'active' | 'inactive';
    riskEngine: 'active' | 'inactive';
  };
}

/**
 * Determine risk level from numeric score (0-100)
 */
export const getRiskLevel = (score: number): RiskLevel => {
  if (score < 30) return 'LOW';
  if (score < 60) return 'MEDIUM';
  if (score < 80) return 'HIGH';
  return 'CRITICAL';
};

/**
 * Pure Idle state - Normal startup with no active calls or simulated data
 */
export const getIdleDashboardState = (): DashboardState => ({
  connectionStatus: 'online',
  callStatus: 'idle',
  callDuration: 0,
  callerIdentity: 'No Active Call',
  audioStreamActive: false,
  
  riskScore: 0,
  riskLevel: 'LOW',
  
  voice: {
    score: 0,
    isSpoof: false,
    confidence: 'IDLE',
    model: 'Spectra-AASIST3'
  },
  
  conversation: {
    urgency: 0,
    authorityImpersonation: 0,
    financialRequest: 0,
    credentialRequest: 0,
    threat: 0
  },
  
  transcript: [],
  events: [],
  recommendation: {
    action: '',
    description: ''
  },
  
  riskFactors: [],
  
  systemComponents: {
    voiceAnalysis: 'inactive',
    speechTranscription: 'inactive',
    conversationAnalysis: 'inactive',
    riskEngine: 'inactive'
  }
});

/**
 * Step progression for Demo Mode (SIH Presentation Simulation)
 */
export interface DemoStep {
  step: number;
  timeOffsetSec: number;
  duration: number;
  callerIdentity: string;
  riskScore: number;
  voice: VoiceAnalysisData;
  conversation: ConversationAnalysisData;
  transcriptNewMessage?: TranscriptMessage;
  eventsNewEvent?: RiskFeedEvent;
  recommendation?: {
    action: string;
    description: string;
  };
  riskFactors: RiskFactor[];
}

export const DEMO_PROGRESSION: DemoStep[] = [
  // Step 0: Call incoming and connects, normal greeting
  {
    step: 0,
    timeOffsetSec: 0,
    duration: 3,
    callerIdentity: 'Unknown (+1 800-432-1000)',
    riskScore: 14,
    voice: {
      score: 12,
      isSpoof: false,
      confidence: 'Normal Acoustic',
      model: 'Spectra-AASIST3'
    },
    conversation: {
      urgency: 10,
      authorityImpersonation: 15,
      financialRequest: 0,
      credentialRequest: 0,
      threat: 0
    },
    transcriptNewMessage: {
      id: 'demo-1',
      timestamp: '00:02',
      speaker: 'caller',
      text: "Hello, this is officer Davies calling from Federal Trust Bank fraud division."
    },
    eventsNewEvent: {
      id: 'evt-1',
      timestamp: '00:02',
      message: 'Incoming voice call connected',
      severity: 'info',
      source: 'audio'
    },
    recommendation: {
      action: 'MONITORING CALL',
      description: 'Listening for speech biometric anomalies and conversational social-engineering cues.'
    },
    riskFactors: [
      {
        id: 'voice-auth',
        name: 'Voice Biometrics',
        status: 'clear',
        description: 'Analyzing spectral harmonics and phase distribution.'
      }
    ]
  },
  // Step 1: Acoustic spoof signs detected
  {
    step: 1,
    timeOffsetSec: 3,
    duration: 7,
    callerIdentity: 'Federal Trust Bank (Unverified)',
    riskScore: 42,
    voice: {
      score: 64,
      isSpoof: true,
      confidence: 'Acoustic Anomaly Detected',
      model: 'Spectra-AASIST3'
    },
    conversation: {
      urgency: 25,
      authorityImpersonation: 55,
      financialRequest: 10,
      credentialRequest: 0,
      threat: 0
    },
    transcriptNewMessage: {
      id: 'demo-2',
      timestamp: '00:06',
      speaker: 'caller',
      text: "We have intercepted an unauthorized wire attempt on your account for $8,920."
    },
    eventsNewEvent: {
      id: 'evt-2',
      timestamp: '00:06',
      message: 'Acoustic spoof indicators detected (synthetic voice artifact)',
      severity: 'warning',
      source: 'voice'
    },
    recommendation: {
      action: 'EXERCISE CAUTION',
      description: 'Voice frequency anomalies detected. Do not share sensitive personal information.'
    },
    riskFactors: [
      {
        id: 'voice-spoofing',
        name: 'Voice Spoofing Indicators',
        status: 'suspected',
        description: 'Spectra-AASIST3 detected phase discontinuities and synthetic vocoder spectral cues.'
      },
      {
        id: 'authority-claim',
        name: 'Institution Identity Claim',
        status: 'suspected',
        description: 'Caller claims official banking identity without verifiable cryptographic signature.'
      }
    ]
  },
  // Step 2: Authority Impersonation & Urgency pressure
  {
    step: 2,
    timeOffsetSec: 7,
    duration: 12,
    callerIdentity: 'Federal Trust Bank (Spoof Suspected)',
    riskScore: 71,
    voice: {
      score: 79,
      isSpoof: true,
      confidence: 'High Spoof Probability',
      model: 'Spectra-AASIST3'
    },
    conversation: {
      urgency: 85,
      authorityImpersonation: 88,
      financialRequest: 30,
      credentialRequest: 40,
      threat: 65
    },
    transcriptNewMessage: {
      id: 'demo-3',
      timestamp: '00:11',
      speaker: 'caller',
      text: "You must confirm your authorization immediately, or we will freeze all accounts in 5 minutes."
    },
    eventsNewEvent: {
      id: 'evt-3',
      timestamp: '00:11',
      message: 'High urgency & threat language detected (GPT-OSS)',
      severity: 'warning',
      source: 'nlp'
    },
    recommendation: {
      action: 'SUSPICIOUS CALL — DO NOT COMPLY',
      description: 'Severe urgency and authority pressure detected. Financial institutions never demand instant action under threat of asset freeze.'
    },
    riskFactors: [
      {
        id: 'voice-spoofing',
        name: 'Voice Spoofing',
        status: 'detected',
        description: 'Spectra-AASIST3 confirmed synthetic audio characteristics with 79% model confidence.'
      },
      {
        id: 'urgency-tactic',
        name: 'Urgency / Time Pressure',
        status: 'detected',
        description: 'Artificial deadline (5-minute freeze) used to bypass critical thinking.'
      },
      {
        id: 'authority-impersonation',
        name: 'Authority Impersonation',
        status: 'detected',
        description: 'Impersonating bank security official.'
      }
    ]
  },
  // Step 3: Financial Request / Instruction to wire money
  {
    step: 3,
    timeOffsetSec: 12,
    duration: 18,
    callerIdentity: 'FLAGGED: Voice Cloning Attack',
    riskScore: 89,
    voice: {
      score: 88,
      isSpoof: true,
      confidence: 'Cloned Voice Confirmed',
      model: 'Spectra-AASIST3'
    },
    conversation: {
      urgency: 95,
      authorityImpersonation: 94,
      financialRequest: 92,
      credentialRequest: 70,
      threat: 85
    },
    transcriptNewMessage: {
      id: 'demo-4',
      timestamp: '00:16',
      speaker: 'caller',
      text: "Transfer remaining funds into our Federal Reserve Escrow Account 4920-1102-8831 immediately."
    },
    eventsNewEvent: {
      id: 'evt-4',
      timestamp: '00:16',
      message: 'Financial fund transfer instruction detected',
      severity: 'critical',
      source: 'nlp'
    },
    recommendation: {
      action: 'DO NOT TRANSFER FUNDS',
      description: 'Active voice cloning & financial scam detected. Hang up immediately. Verify caller via the phone number on your card.'
    },
    riskFactors: [
      {
        id: 'voice-spoofing',
        name: 'Voice Cloning Attack',
        status: 'detected',
        description: 'Synthetic voice model matched against deepfake acoustic signature.'
      },
      {
        id: 'financial-instruction',
        name: 'Fund Transfer Instruction',
        status: 'detected',
        description: 'Explicit instruction to divert funds to an external routing number.'
      },
      {
        id: 'urgency-threat',
        name: 'Urgency & Coercion',
        status: 'detected',
        description: 'High-pressure coercion tactics identified.'
      }
    ]
  },
  // Step 4: Final Critical Escalation
  {
    step: 4,
    timeOffsetSec: 18,
    duration: 25,
    callerIdentity: 'FLAGGED: CRITICAL IMPERSONATION',
    riskScore: 96,
    voice: {
      score: 94,
      isSpoof: true,
      confidence: 'Deepfake Confirmed (94%)',
      model: 'Spectra-AASIST3'
    },
    conversation: {
      urgency: 98,
      authorityImpersonation: 98,
      financialRequest: 98,
      credentialRequest: 80,
      threat: 90
    },
    eventsNewEvent: {
      id: 'evt-5',
      timestamp: '00:20',
      message: 'Risk Engine escalated threat level to CRITICAL',
      severity: 'critical',
      source: 'engine'
    },
    recommendation: {
      action: 'DO NOT TRANSFER FUNDS — TERMINATE CALL',
      description: 'Multi-vector verification failure: Deepfake voice confirmed + Social engineering financial transfer demand.'
    },
    riskFactors: [
      {
        id: 'voice-spoofing',
        name: 'Acoustic Voice Spoofing',
        status: 'detected',
        description: 'Spectra-AASIST3 deepfake detection score 94/100.'
      },
      {
        id: 'social-engineering',
        name: 'Multi-Vector Social Engineering',
        status: 'detected',
        description: 'Combined bank impersonation, urgency countdown, and fraudulent escrow routing.'
      }
    ]
  }
];

/**
 * Legacy getter for full mock state
 */
export const getMockDashboardState = (): DashboardState => {
  const lastStep = DEMO_PROGRESSION[DEMO_PROGRESSION.length - 1];
  const allMessages: TranscriptMessage[] = [];
  const allEvents: RiskFeedEvent[] = [];

  DEMO_PROGRESSION.forEach(s => {
    if (s.transcriptNewMessage) allMessages.push(s.transcriptNewMessage);
    if (s.eventsNewEvent) allEvents.push(s.eventsNewEvent);
  });

  return {
    connectionStatus: 'online',
    callStatus: 'live',
    callDuration: 24,
    callerIdentity: lastStep.callerIdentity,
    audioStreamActive: true,
    riskScore: lastStep.riskScore,
    riskLevel: getRiskLevel(lastStep.riskScore),
    voice: lastStep.voice,
    conversation: lastStep.conversation,
    transcript: allMessages,
    events: allEvents,
    recommendation: lastStep.recommendation!,
    riskFactors: lastStep.riskFactors,
    systemComponents: {
      voiceAnalysis: 'active',
      speechTranscription: 'active',
      conversationAnalysis: 'active',
      riskEngine: 'active'
    }
  };
};

export const getRiskLevelLabel = (score: number): string => {
  return getRiskLevel(score);
};
