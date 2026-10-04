/**
 * Light or dark theme. With no saved choice the page follows the system setting
 * (CSS light-dark() on color-scheme: light dark); a choice is saved per browser and
 * applied before first paint by the inline script in index.html and share.html.
 */
export type Theme = 'light' | 'dark';

export const THEME_KEY = 'pp-theme';
// The page ground per theme, for the browser's toolbar colour (keep in step with --bg).
const THEME_COLORS: Record<Theme, string> = { light: '#edf3f1', dark: '#061012' };

export function storedTheme(): Theme | null {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}

export function systemTheme(): Theme {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/** The theme the page is showing: the reader's choice, otherwise the system's. */
export function currentTheme(): Theme {
  const chosen = document.documentElement.getAttribute('data-theme');
  return chosen === 'light' || chosen === 'dark' ? chosen : systemTheme();
}

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Private mode or blocked storage: the choice lasts for this page only.
  }
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach((meta) => {
    meta.content = THEME_COLORS[theme];
  });
}
