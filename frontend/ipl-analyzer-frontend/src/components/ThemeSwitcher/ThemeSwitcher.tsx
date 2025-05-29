import React, { useState, useEffect } from 'react';
import './ThemeSwitcher.css';

const ThemeSwitcher: React.FC = () => {
  const [currentBaseTheme, setCurrentBaseTheme] = useState<string>('new-theme');
  const [currentMode, setCurrentMode] = useState<string>('light');

  // Effect for initial load: load from localStorage or set defaults
  useEffect(() => {
    const savedBaseTheme = localStorage.getItem('appBaseTheme');
    const savedMode = localStorage.getItem('appMode');

    let initialBaseTheme = 'new-theme';
    let initialMode = 'light';

    if (savedBaseTheme) {
      initialBaseTheme = savedBaseTheme;
    }
    if (savedMode) {
      initialMode = savedMode;
    }

    setCurrentBaseTheme(initialBaseTheme);
    setCurrentMode(initialMode);

    // Apply theme directly here as well to ensure it's set on first load
    // The second useEffect will also run, but this ensures immediate application
    document.documentElement.setAttribute('data-base-theme', initialBaseTheme);
    document.documentElement.setAttribute('data-mode', initialMode);
    
    // Save to localStorage if it wasn't already set (i.e., first visit with defaults)
    if (!savedBaseTheme) {
      localStorage.setItem('appBaseTheme', initialBaseTheme);
    }
    if (!savedMode) {
      localStorage.setItem('appMode', initialMode);
    }
  }, []); // Empty dependency array ensures this runs only on mount

  // Effect for theme changes: update localStorage and HTML attributes
  useEffect(() => {
    localStorage.setItem('appBaseTheme', currentBaseTheme);
    localStorage.setItem('appMode', currentMode);

    document.documentElement.setAttribute('data-base-theme', currentBaseTheme);
    document.documentElement.setAttribute('data-mode', currentMode);
  }, [currentBaseTheme, currentMode]);

  const handleBaseThemeChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setCurrentBaseTheme(event.target.value);
  };

  const handleModeChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setCurrentMode(event.target.value);
  };

  return (
    <div className="theme-switcher">
      <div>
        <label htmlFor="theme-select">Theme:</label>
        <select id="theme-select" value={currentBaseTheme} onChange={handleBaseThemeChange}>
          <option value="new-theme">New Theme</option>
          <option value="legacy-orange-blue">Legacy Theme</option>
        </select>
      </div>
      <div>
        <label htmlFor="mode-select">Mode:</label>
        <select id="mode-select" value={currentMode} onChange={handleModeChange}>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </div>
    </div>
  );
};

export default ThemeSwitcher;
