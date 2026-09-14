import { RiskFactor } from '../data/mockData';
import './RiskFactors.css';

interface RiskFactorsProps {
  factors: RiskFactor[];
}

export const RiskFactors: React.FC<RiskFactorsProps> = ({ factors }) => {
  const isIdle = factors.length === 0;

  return (
    <div className="risk-factors">
      <div className="risk-factors-header">
        <h2>Risk Factors</h2>
      </div>
      
      {isIdle ? (
        <div className="risk-factors-idle">
          <p>No active signals</p>
        </div>
      ) : (
        <div className="risk-factors-list">
          {factors.map((factor) => (
            <div
              key={factor.id}
              className={`risk-factor-card ${factor.status}`}
            >
              <div className="factor-name">{factor.name}</div>
              <div className={`factor-status ${factor.status}`}>
                {factor.status === 'detected' ? 'DETECTED' :
                 factor.status === 'suspected' ? 'SUSPECTED' :
                 'CLEAR'}
              </div>
              <div className="factor-description">{factor.description}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
