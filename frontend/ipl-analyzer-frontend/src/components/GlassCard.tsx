import React, { type ReactNode } from 'react';
import styles from './GlassCard.module.css';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  // Add other props like 'as' for polymorphic component if needed later
}

const GlassCard: React.FC<GlassCardProps> = ({ children, className = '' }) => {
  const combinedClassName = `${styles.card} ${className}`.trim();

  return (
    <div className={combinedClassName}>
      {children}
    </div>
  );
};

export default GlassCard;
