import React from 'react';
import { useTheme } from '../contexts/ThemeContext';
import styles from './ThemeToggle.module.css';

const ThemeToggle: React.FC = () => {
  const { currentMode, setMode } = useTheme(); // UPDATED to use currentMode and setMode

  const themes: { value: 'light' | 'dark' | 'system'; label: string }[] = [
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
    { value: 'system', label: 'System' },
  ];

  return (
    <div className={styles.toggleContainer} role="radiogroup" aria-label="Theme selection">
      {themes.map((t) => (
        <button
          key={t.value}
          className={`${styles.toggleButton} ${currentMode === t.value ? styles.active : ''}`} // UPDATED to use currentMode
          onClick={() => setMode(t.value)} // UPDATED to use setMode
          role="radio"
          aria-checked={currentMode === t.value} // UPDATED to use currentMode
          aria-label={`Select ${t.label} theme`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
};

export default ThemeToggle;
