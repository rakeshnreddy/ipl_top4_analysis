import React, { createContext, useContext, useEffect, useState, type ReactNode, useCallback } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
export type BasePalette = 'default-orange-blue' | 'oceanic-teal' | 'ruby-radiance'; // Add more as they are defined

// Define a list of available palettes for the PaletteSwitcher later
export const availablePalettes: { key: BasePalette; name: string }[] = [
  { key: 'default-orange-blue', name: 'Default Orange/Blue' },
  { key: 'oceanic-teal', name: 'Oceanic Teal' },
  { key: 'ruby-radiance', name: 'Ruby Radiance' },
  // Add more palettes here as they are defined in CSS
];

interface ThemeContextType {
  currentMode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  currentBasePalette: BasePalette;
  setBasePalette: (palette: BasePalette) => void;
  effectiveTheme: 'light' | 'dark'; // Actual mode being applied (light or dark)
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentMode, setCurrentModeState] = useState<ThemeMode>(() => {
    return (localStorage.getItem('themeMode') as ThemeMode) || 'system';
  });

  const [currentBasePalette, setCurrentBasePaletteState] = useState<BasePalette>(() => {
    return (localStorage.getItem('basePalette') as BasePalette) || 'default-orange-blue';
  });

  const [effectiveTheme, setEffectiveTheme] = useState<'light' | 'dark'>('light');

  const applyActiveTheme = useCallback(() => {
    let modeToApply: 'light' | 'dark';
    if (currentMode === 'system') {
      modeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } else {
      modeToApply = currentMode;
    }

    setEffectiveTheme(modeToApply);
    document.documentElement.setAttribute('data-base-theme', currentBasePalette);
    document.documentElement.setAttribute('data-mode', modeToApply);
    
    localStorage.setItem('themeMode', currentMode);
    localStorage.setItem('basePalette', currentBasePalette);
  }, [currentMode, currentBasePalette]);

  useEffect(() => {
    applyActiveTheme();
  }, [applyActiveTheme]); // applyActiveTheme is stable due to its own dependencies

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (currentMode === 'system') {
        applyActiveTheme(); // Re-apply based on new system preference
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [currentMode, applyActiveTheme]);

  const setMode = (newMode: ThemeMode) => {
    setCurrentModeState(newMode);
  };

  const setBasePalette = (newPalette: BasePalette) => {
    setCurrentBasePaletteState(newPalette);
  };
  
  return (
    <ThemeContext.Provider value={{ currentMode, setMode, currentBasePalette, setBasePalette, effectiveTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
