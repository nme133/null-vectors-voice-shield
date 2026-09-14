import './RecommendedAction.css';

interface RecommendedActionProps {
  action: string;
  description: string;
}

export const RecommendedAction: React.FC<RecommendedActionProps> = ({
  action,
  description
}) => {
  const isIdle = !action;

  return (
    <div className={`recommended-action ${isIdle ? 'idle' : 'active'}`}>
      {isIdle ? (
        <div className="action-idle">
          <p>No active recommendation</p>
        </div>
      ) : (
        <div className="action-alert">
          <div className="alert-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
            </svg>
          </div>
          <div className="alert-content">
            <div className="alert-action">{action}</div>
            <div className="alert-description">{description}</div>
          </div>
        </div>
      )}
    </div>
  );
};
