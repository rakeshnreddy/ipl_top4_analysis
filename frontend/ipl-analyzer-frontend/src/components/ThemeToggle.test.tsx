/// <reference types="vitest/globals" />
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, useTheme } from '../contexts/ThemeContext';
import ThemeToggle from './ThemeToggle';
import styles from './ThemeToggle.module.css'; // Import CSS Modules

// Mock ThemeContext for more controlled testing if needed,
// but often testing through ThemeProvider is more robust.

// Mock window.matchMedia for ThemeContext
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
      matches: false, // Default to light theme for system preference in tests
      media: query,
      onchange: null,
      addListener: vi.fn(), // Deprecated but included for completeness
      removeListener: vi.fn(), // Deprecated
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
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
    // This depends on ThemeProvider's default. Let's assume it's 'system'.
    // Or we can mock localStorage.getItem('theme') to return 'system'.
    expect(screen.getByRole('radio', { name: /Select System theme/i })).toHaveClass(styles.active);
  });

  it('Test 3: Calls setTheme when a button is clicked', () => {
    // It's hard to verify actual theme change without deeper mocking or visual inspection.
    // We can test if the button click attempts to set the theme.
    // For this, we might need to mock part of ThemeContext or spy on setTheme.
    // A simpler way is to check if the active class changes.

    // Spy on localStorage.setItem as an indirect way to see if setTheme logic runs
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');

    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    const lightButton = screen.getByRole('radio', { name: /Select Light theme/i });
    fireEvent.click(lightButton);
    
    // Check if localStorage was called (part of setTheme in context)
    expect(setItemSpy).toHaveBeenCalledWith('theme', 'light');
    // Check if active class updates
    expect(lightButton).toHaveClass(styles.active);
    expect(screen.getByRole('radio', { name: /Select System theme/i })).not.toHaveClass(styles.active);

    setItemSpy.mockRestore(); // Clean up spy
  });
});
