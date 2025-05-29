import React from 'react';
import { useTheme, availablePalettes } from '../contexts/ThemeContext'; // Removed unused BasePalette type
import styles from './PaletteSwitcher.module.css';

const PaletteSwitcher: React.FC = () => {
  const { currentBasePalette, setBasePalette } = useTheme();

  return (
    <div className={styles.switcherContainer} role="radiogroup" aria-labelledby="palette-switcher-label">
      <span id="palette-switcher-label" className={styles.label}>Palette:</span>
      {availablePalettes.map((palette) => (
        <button
          key={palette.key}
          className={`${styles.paletteButton} ${currentBasePalette === palette.key ? styles.active : ''}`}
          onClick={() => setBasePalette(palette.key)}
          role="radio"
          aria-checked={currentBasePalette === palette.key}
          aria-label={`Select ${palette.name} palette`}
        >
          {palette.name}
        </button>
      ))}
    </div>
  );
};

export default PaletteSwitcher;
