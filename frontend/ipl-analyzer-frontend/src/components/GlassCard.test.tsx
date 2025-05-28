/// <reference types="vitest/globals" />
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GlassCard from './GlassCard';
import styles from './GlassCard.module.css'; // To check against actual class name

describe('GlassCard Component', () => {
  it('Test 1: Renders children correctly', () => {
    render(
      <GlassCard>
        <p>Test Child</p>
      </GlassCard>
    );
    expect(screen.getByText('Test Child')).toBeInTheDocument();
  });

  it('Test 2: Applies the base card style', () => {
    const { container } = render(<GlassCard>Content</GlassCard>);
    // Check if the first child (the div rendered by GlassCard) has the specific module class name
    expect(container.firstChild).toHaveClass(styles.card);
  });

  it('Test 3: Applies additional className when provided', () => {
    const customClass = 'my-custom-card-style';
    const { container } = render(<GlassCard className={customClass}>Content</GlassCard>);
    expect(container.firstChild).toHaveClass(styles.card);
    expect(container.firstChild).toHaveClass(customClass);
  });

  it('Test 4: Renders correctly and matches snapshot', () => {
    const { container } = render(
      <GlassCard className="extra-class">
        <span>Snapshot Content</span>
      </GlassCard>
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
