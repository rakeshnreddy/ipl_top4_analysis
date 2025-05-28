import React from 'react';
import { useTheme } from '../contexts/ThemeContext';
import styles from './ThemeToggle.module.css';

const ThemeToggle: React.FC = () => {
  const { theme, setTheme } = useTheme();

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
          className={`${styles.toggleButton} ${theme === t.value ? styles.active : ''}`}
          onClick={() => setTheme(t.value)}
          role="radio"
          aria-checked={theme === t.value}
          aria-label={`Select ${t.label} theme`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
};

export default ThemeToggle;
