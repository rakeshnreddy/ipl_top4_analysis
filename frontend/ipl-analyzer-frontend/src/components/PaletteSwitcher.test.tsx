/// <reference types="vitest/globals" />
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, availablePalettes } from '../contexts/ThemeContext'; // Import availablePalettes
import PaletteSwitcher from './PaletteSwitcher';
import styles from './PaletteSwitcher.module.css';

describe('PaletteSwitcher Component', () => {
  beforeAll(() => {
    // Mock window.matchMedia for ThemeProvider system preference check
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(query => ({
        matches: false, // Default to light mode for system preference in tests
        media: query,
        onchange: null,
        addListener: vi.fn(), // Deprecated but Vitest JSDOM might need it
        removeListener: vi.fn(), // Deprecated
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it('Test 1: Renders buttons for available palettes', () => {
    render(
      <ThemeProvider>
        <PaletteSwitcher />
      </ThemeProvider>
    );
    availablePalettes.forEach(palette => {
      expect(screen.getByRole('radio', { name: `Select ${palette.name} palette` })).toBeInTheDocument();
    });
  });

  it('Test 2: Highlights the active palette button (default "default-orange-blue")', () => {
    render(
      <ThemeProvider>
        <PaletteSwitcher />
      </ThemeProvider>
    );
    const defaultPalette = availablePalettes.find(p => p.key === 'default-orange-blue');
    expect(screen.getByRole('radio', { name: `Select ${defaultPalette!.name} palette` })).toHaveClass(styles.active);
  });

  it('Test 3: Persists the available palette selection on click', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    render(
      <ThemeProvider>
        <PaletteSwitcher />
      </ThemeProvider>
    );

    const defaultPalette = availablePalettes.find(p => p.key === 'default-orange-blue');
    const defaultButton = screen.getByRole('radio', { name: `Select ${defaultPalette!.name} palette` });
    
    fireEvent.click(defaultButton);
    
    expect(setItemSpy).toHaveBeenCalledWith('basePalette', 'default-orange-blue');
    expect(defaultButton).toHaveClass(styles.active);

    setItemSpy.mockRestore();
  });
});
