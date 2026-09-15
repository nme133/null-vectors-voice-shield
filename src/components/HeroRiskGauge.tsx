import React from 'react';
import { RiskLevel } from '../data/mockData';
import './HeroRiskGauge.css';

interface HeroRiskGaugeProps {
  score: number;
  level: RiskLevel;
  isActive: boolean;
}

export const HeroRiskGauge: React.FC<HeroRiskGaugeProps> = ({
  score,
  level,
  isActive
}) => {
  // SVG circular geometry
  const size = 280;
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const center = size / 2;
  // Use 270 degree arc for a commanding instrument gauge look
  const startAngle = 135;
  const totalArc = 270;
  
  // Circumference for full circle
  const circumference = 2 * Math.PI * radius;
  // Circumference portion for the 270 degree arc
  const arcLength = (totalArc / 360) * circumference;
  
  // Clamped score between 0 and 100
  const normalizedScore = Math.max(0, Math.min(100, score));
  // Progress along the arc
  const progressLength = (normalizedScore / 100) * arcLength;
  const strokeDashoffset = arcLength - progressLength;

  // Level color class
  const levelClass = !isActive && score === 0 ? 'idle' : level.toLowerCase();

  return (
    <div className={`hero-risk-gauge-container ${levelClass}`}>
      <div className="gauge-frame">
        <svg
          className="gauge-svg"
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
        >
          <defs>
            <linearGradient id="gaugeGradLow" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#059669" />
            </linearGradient>
            <linearGradient id="gaugeGradMedium" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f59e0b" />
              <stop offset="100%" stopColor="#d97706" />
            </linearGradient>
            <linearGradient id="gaugeGradHigh" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f97316" />
              <stop offset="100%" stopColor="#ea580c" />
            </linearGradient>
            <linearGradient id="gaugeGradCritical" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="100%" stopColor="#b91c1c" />
            </linearGradient>
            <linearGradient id="gaugeGradIdle" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="rgba(255, 255, 255, 0.15)" />
              <stop offset="100%" stopColor="rgba(255, 255, 255, 0.05)" />
            </linearGradient>

            <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Outer technical tick marks */}
          <circle
            cx={center}
            cy={center}
            r={radius + 12}
            className="gauge-tick-track"
            strokeDasharray="2, 8"
          />

          {/* Background Arc Track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            className="gauge-track"
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            style={{
              transformOrigin: 'center',
              transform: `rotate(${startAngle}deg)`
            }}
          />

          {/* Animated Active Progress Arc */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            className={`gauge-progress ${levelClass}`}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={strokeDashoffset}
            filter="url(#gaugeGlow)"
            style={{
              transformOrigin: 'center',
              transform: `rotate(${startAngle}deg)`
            }}
          />
        </svg>

        {/* Center Content Display */}
        <div className="gauge-center-content">
          <span className="gauge-caption">CURRENT THREAT LEVEL</span>
          <div className="gauge-score-row">
            <span className="gauge-score-value">{isActive || score > 0 ? score : '00'}</span>
            <span className="gauge-score-denom">/ 100</span>
          </div>
          <div className={`gauge-badge ${levelClass}`}>
            <span className="badge-pulse-dot"></span>
            <span className="badge-text">
              {!isActive && score === 0 ? 'SYSTEM IDLE' : level}
            </span>
          </div>
          <span className="gauge-subcaption">
            {!isActive && score === 0 ? 'NO ACTIVE CALL' : 'REAL-TIME RISK ENGINE'}
          </span>
        </div>
      </div>

      {/* Threat Band Scale Legend */}
      <div className="gauge-scale-bar">
        <div className={`scale-segment low ${level === 'LOW' && (isActive || score > 0) ? 'active' : ''}`}>
          <span className="scale-dot"></span>
          <span className="scale-label">0–29 LOW</span>
        </div>
        <div className={`scale-segment medium ${level === 'MEDIUM' && (isActive || score > 0) ? 'active' : ''}`}>
          <span className="scale-dot"></span>
          <span className="scale-label">30–59 MED</span>
        </div>
        <div className={`scale-segment high ${level === 'HIGH' && (isActive || score > 0) ? 'active' : ''}`}>
          <span className="scale-dot"></span>
          <span className="scale-label">60–79 HIGH</span>
        </div>
        <div className={`scale-segment critical ${level === 'CRITICAL' && (isActive || score > 0) ? 'active' : ''}`}>
          <span className="scale-dot"></span>
          <span className="scale-label">80–100 CRIT</span>
        </div>
      </div>
    </div>
  );
};
