import { getRiskLevelLabel } from '../data/mockData';
import './RiskScore.css';

interface RiskScoreProps {
  score: number;
}

export const RiskScore: React.FC<RiskScoreProps> = ({ score }) => {
  const riskLevel = getRiskLevelLabel(score);
  const isIdle = score === 0;
  
  // Calculate rotation for gauge (0-100 maps to 0-180 degrees)
  const rotation = (score / 100) * 180 - 90;
  
  // Determine color class based on score
  let colorClass = 'low';
  if (score >= 30 && score < 60) colorClass = 'medium';
  else if (score >= 60 && score < 80) colorClass = 'high';
  else if (score >= 80) colorClass = 'critical';
  
  return (
    <div className="risk-score">
      <div className="risk-score-header">
        <h2>Risk Score</h2>
      </div>
      
      {isIdle ? (
        <div className="risk-score-idle">
          <div className="idle-message">NO ACTIVE CALL</div>
          <p>Start monitoring to begin analysis</p>
        </div>
      ) : (
        <>
          <div className={`risk-score-container ${colorClass}`}>
            {/* Gauge Background */}
            <svg className="risk-gauge" viewBox="0 0 200 120" xmlns="http://www.w3.org/2000/svg">
              {/* Gauge background arc */}
              <path
                d="M 30 100 A 70 70 0 0 1 170 100"
                fill="none"
                stroke="rgba(255, 255, 255, 0.1)"
                strokeWidth="12"
                strokeLinecap="round"
              />
              
              {/* Risk level background segments */}
              <path
                d="M 30 100 A 70 70 0 0 1 70 42.5"
                fill="none"
                stroke="rgba(34, 197, 94, 0.3)"
                strokeWidth="12"
                strokeLinecap="round"
              />
              <path
                d="M 70 42.5 A 70 70 0 0 1 130 42.5"
                fill="none"
                stroke="rgba(234, 179, 8, 0.3)"
                strokeWidth="12"
                strokeLinecap="round"
              />
              <path
                d="M 130 42.5 A 70 70 0 0 1 170 100"
                fill="none"
                stroke="rgba(239, 68, 68, 0.3)"
                strokeWidth="12"
                strokeLinecap="round"
              />
              
              {/* Colored indicator arc based on score */}
              <g>
                <defs>
                  <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#22c55e" />
                    <stop offset="30%" stopColor="#eab308" />
                    <stop offset="70%" stopColor="#f97316" />
                    <stop offset="100%" stopColor="#ef4444" />
                  </linearGradient>
                </defs>
                <path
                  d={score <= 50 ? 
                    `M 30 100 A 70 70 0 0 1 ${30 + Math.cos((score / 100) * Math.PI - Math.PI / 2) * 70} ${100 + Math.sin((score / 100) * Math.PI - Math.PI / 2) * 70}` :
                    `M 30 100 A 70 70 0 0 1 ${30 + Math.cos((score / 100) * Math.PI - Math.PI / 2) * 70} ${100 + Math.sin((score / 100) * Math.PI - Math.PI / 2) * 70}`
                  }
                  fill="none"
                  stroke="url(#riskGradient)"
                  strokeWidth="12"
                  strokeLinecap="round"
                />
              </g>
              
              {/* Needle/indicator */}
              <line
                x1="100"
                y1="100"
                x2={100 + Math.cos(rotation * Math.PI / 180) * 65}
                y2={100 + Math.sin(rotation * Math.PI / 180) * 65}
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />
              
              {/* Center circle */}
              <circle cx="100" cy="100" r="6" fill="currentColor" />
            </svg>
            
            {/* Score Display */}
            <div className="risk-score-display">
              <div className="score-number">{score}</div>
              <div className="score-max">/ 100</div>
            </div>
          </div>
          
          {/* Risk Level Label */}
          <div className={`risk-level-label ${colorClass}`}>
            {riskLevel}
          </div>
          
          {/* Legend */}
          <div className="risk-legend">
            <div className="legend-item">
              <span className="legend-color low"></span>
              <span className="legend-text">0–29 Low</span>
            </div>
            <div className="legend-item">
              <span className="legend-color medium"></span>
              <span className="legend-text">30–59 Medium</span>
            </div>
            <div className="legend-item">
              <span className="legend-color high"></span>
              <span className="legend-text">60–79 High</span>
            </div>
            <div className="legend-item">
              <span className="legend-color critical"></span>
              <span className="legend-text">80–100 Critical</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
