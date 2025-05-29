/// <reference types="vitest/globals" />
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '../contexts/ThemeContext'; // Removed unused useTheme
import ThemeToggle from './ThemeToggle';
import styles from './ThemeToggle.module.css'; // Import CSS Modules

// Mock ThemeContext for more controlled testing if needed,
// but often testing through ThemeProvider is more robust.

// Mock window.matchMedia for ThemeContext
beforeEach(() => { // Changed from beforeAll to beforeEach
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
      matches: false, // Default to light theme for system preference in tests
      media: query,
      onchange: null,
      addListener: vi.fn(), 
      removeListener: vi.fn(), 
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
  // Clear localStorage for themeMode to ensure consistent default state for relevant tests
  localStorage.removeItem('themeMode');
  localStorage.removeItem('basePalette'); // Also clear basePalette for good measure
});

describe('ThemeToggle Component', () => {
  it('Test 1: Renders buttons for Light, Dark, System', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );
    expect(screen.getByRole('radio', { name: /Select Light theme/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Select Dark theme/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Select System theme/i })).toBeInTheDocument();
  });

  it('Test 2: Highlights the active theme button (default or initial)', () => {
    // Assuming 'system' is the default or initial theme from localStorage mock if any
    // Or, wrap with a provider that has a specific initial theme for testing
    render(
      <ThemeProvider> {/* ThemeProvider will default to 'system' or localStorage */}
        <ThemeToggle />
      </ThemeProvider>
    );
    // Default initial themeMode is 'system' due to ThemeContext and beforeEach localStorage.clear
    expect(screen.getByRole('radio', { name: /Select System theme/i })).toHaveClass(styles.active);
    expect(screen.getByRole('radio', { name: /Select Light theme/i })).not.toHaveClass(styles.active);
    expect(screen.getByRole('radio', { name: /Select Dark theme/i })).not.toHaveClass(styles.active);
  });

  it('Test 3: Calls setMode and updates active class on click, also checks localStorage', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    const lightButton = screen.getByRole('radio', { name: /Select Light theme/i });
    fireEvent.click(lightButton);
    
    // Check if localStorage was called with the correct key and value for themeMode
    expect(setItemSpy).toHaveBeenCalledWith('themeMode', 'light');
    // Check if active class updates
    expect(lightButton).toHaveClass(styles.active);
    expect(screen.getByRole('radio', { name: /Select System theme/i })).not.toHaveClass(styles.active);

    // Now click Dark button
    const darkButton = screen.getByRole('radio', { name: /Select Dark theme/i });
    fireEvent.click(darkButton);
    expect(setItemSpy).toHaveBeenCalledWith('themeMode', 'dark');
    expect(darkButton).toHaveClass(styles.active);
    expect(lightButton).not.toHaveClass(styles.active);

    setItemSpy.mockRestore();
  });
});
