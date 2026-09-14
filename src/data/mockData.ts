// Mock data for VoxShield Dashboard
// This data is structured to be easily replaced with WebSocket messages from the backend

export interface TimelineEvent {
  timestamp: string;
  message: string;
  type: 'info' | 'warning' | 'critical';
}

export interface RiskFactor {
  id: string;
  name: string;
  status: 'detected' | 'suspected' | 'clear';
  description: string;
}

export interface TranscriptMessage {
  id: string;
  timestamp: string;
  speaker: 'caller' | 'user';
  text: string;
}

export interface DashboardState {
  // Connection
  connectionStatus: 'online' | 'offline';
  
  // Call Status
  callStatus: 'live' | 'ended' | 'idle';
  callDuration: number; // seconds
  callerIdentity: string;
  audioStreamActive: boolean;
  
  // Risk Score
  riskScore: number; // 0-100
  
  // Voice Authenticity
  voiceAuthModel: string;
  voiceAuthScore: number; // 0-100 model score
  voiceAuthStatus: 'authentic' | 'spoof_suspected' | 'spoof_detected';
  voiceAuthConfidence: string; // Confidence level
  
  // Transcript and Conversation Analysis
  transcript: TranscriptMessage[];
  detectedSignals: {
    authorityImpersonation: boolean;
    urgency: boolean;
    financialRequest: boolean;
    threatFear: boolean;
    instructionToTransfer: boolean;
  };
  
  // Risk Factors
  riskFactors: RiskFactor[];
  
  // Recommended Action
  recommendedAction: string;
  actionDescription: string;
  
  // Event Timeline
  timeline: TimelineEvent[];
  
  // System Status
  systemComponents: {
    voiceAnalysis: 'active' | 'inactive';
    speechTranscription: 'active' | 'inactive';
    conversationAnalysis: 'active' | 'inactive';
    riskEngine: 'active' | 'inactive';
  };
}

export const getIdleDashboardState = (): DashboardState => {
  return {
    connectionStatus: 'online',
    
    callStatus: 'idle',
    callDuration: 0,
    callerIdentity: 'No caller',
    audioStreamActive: false,
    
    riskScore: 0,
    
    voiceAuthModel: 'Spectra-AASIST3',
    voiceAuthScore: 0,
    voiceAuthStatus: 'authentic',
    voiceAuthConfidence: 'N/A',
    
    transcript: [],
    
    detectedSignals: {
      authorityImpersonation: false,
      urgency: false,
      financialRequest: false,
      threatFear: false,
      instructionToTransfer: false
    },
    
    riskFactors: [],
    
    recommendedAction: '',
    actionDescription: '',
    
    timeline: [],
    
    systemComponents: {
      voiceAnalysis: 'inactive',
      speechTranscription: 'inactive',
      conversationAnalysis: 'inactive',
      riskEngine: 'inactive'
    }
  };
};

export const getMockDashboardState = (): DashboardState => {
  return {
    connectionStatus: 'online',
    
    callStatus: 'live',
    callDuration: 43,
    callerIdentity: 'Unknown Caller',
    audioStreamActive: true,
    
    riskScore: 87,
    
    voiceAuthModel: 'Spectra-AASIST3',
    voiceAuthScore: 78,
    voiceAuthStatus: 'spoof_suspected',
    voiceAuthConfidence: 'High',
    
    transcript: [
      {
        id: '1',
        timestamp: '00:12',
        speaker: 'caller',
        text: 'Hello, this is your bank\'s security department.'
      },
      {
        id: '2',
        timestamp: '00:18',
        speaker: 'caller',
        text: 'We detected suspicious activity on your account.'
      },
      {
        id: '3',
        timestamp: '00:27',
        speaker: 'caller',
        text: 'You need to verify your account immediately to prevent fraud.'
      },
      {
        id: '4',
        timestamp: '00:34',
        speaker: 'caller',
        text: 'Please transfer the funds to this secure account: 5241-8837-2910-3847'
      }
    ],
    
    detectedSignals: {
      authorityImpersonation: true,
      urgency: true,
      financialRequest: true,
      threatFear: true,
      instructionToTransfer: true
    },
    
    riskFactors: [
      {
        id: 'voice-spoofing',
        name: 'Voice Spoofing',
        status: 'detected',
        description: 'Audio analysis detected artificial voice characteristics and frequency anomalies consistent with voice cloning.'
      },
      {
        id: 'social-engineering',
        name: 'Social Engineering',
        status: 'detected',
        description: 'Conversation exhibits classic social engineering patterns including authority impersonation and urgency tactics.'
      },
      {
        id: 'urgency-signal',
        name: 'Urgency',
        status: 'detected',
        description: 'Repeated use of time-sensitive language to pressure immediate action.'
      },
      {
        id: 'financial-request',
        name: 'Financial Request',
        status: 'detected',
        description: 'Caller explicitly requesting fund transfer to suspicious account number.'
      },
      {
        id: 'authority-impersonation',
        name: 'Authority Impersonation',
        status: 'detected',
        description: 'Caller claiming to represent official banking institution.'
      }
    ],
    
    recommendedAction: 'DO NOT TRANSFER FUNDS',
    actionDescription: 'This call exhibits multiple indicators of a sophisticated voice cloning attack combined with social engineering. Independently verify the caller by contacting your bank directly using the official phone number on your bank card or statement.',
    
    timeline: [
      {
        timestamp: '00:12',
        message: 'Voice analysis started',
        type: 'info'
      },
      {
        timestamp: '00:18',
        message: 'Suspicious voice characteristics detected',
        type: 'warning'
      },
      {
        timestamp: '00:27',
        message: 'Urgency language detected in conversation',
        type: 'warning'
      },
      {
        timestamp: '00:34',
        message: 'Financial request detected',
        type: 'critical'
      },
      {
        timestamp: '00:41',
        message: 'Risk score increased to 87',
        type: 'critical'
      },
      {
        timestamp: '00:43',
        message: 'HIGH RISK alert triggered',
        type: 'critical'
      }
    ],
    
    systemComponents: {
      voiceAnalysis: 'active',
      speechTranscription: 'active',
      conversationAnalysis: 'active',
      riskEngine: 'active'
    }
  };
};

export const getRiskLevel = (score: number): 'low' | 'medium' | 'high' | 'critical' => {
  if (score < 30) return 'low';
  if (score < 60) return 'medium';
  if (score < 80) return 'high';
  return 'critical';
};

export const getRiskLevelLabel = (score: number): string => {
  const level = getRiskLevel(score);
  return level.toUpperCase();
};
