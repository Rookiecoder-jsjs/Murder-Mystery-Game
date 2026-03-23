// Art Deco Noir theme for murder mystery game

export const theme = {
  colors: {
    // Primary - Deep noir black
    primary: '#0D0D0D',
    primaryLight: '#1A1A1A',
    primaryDark: '#000000',

    // Secondary - Rich burgundy
    secondary: '#8B1538',
    secondaryLight: '#A91D45',
    secondaryDark: '#5C0E25',

    // Accent - Antique gold
    accent: '#D4AF37',
    accentLight: '#E5C158',
    accentDark: '#B8962E',

    // Neutrals
    surface: '#141414',
    surfaceLight: '#1F1F1F',
    card: '#1A1A1A',
    border: '#2A2A2A',

    // Text
    text: '#F5F5F0',
    textSecondary: '#B0B0B0',
    textMuted: '#6A6A6A',

    // Status
    success: '#2D8B4E',
    warning: '#D4AF37',
    danger: '#C41E3A',
    info: '#4A90D9',

    // Clue types
    cluePhysical: '#C9A227',
    clueTestimony: '#4A90D9',
    clueDocument: '#8B5CF6',
  },

  fonts: {
    display: '"Playfair Display", "Noto Serif SC", Georgia, serif',
    body: '"Cormorant Garamond", "Noto Serif SC", Georgia, serif',
    mono: '"JetBrains Mono", "Fira Code", monospace',
  },

  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },

  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
  },

  shadows: {
    sm: '0 2px 8px rgba(212, 175, 55, 0.15)',
    md: '0 4px 16px rgba(212, 175, 55, 0.2)',
    lg: '0 8px 32px rgba(212, 175, 55, 0.25)',
    glow: '0 0 25px rgba(212, 175, 55, 0.35)',
  },

  transitions: {
    fast: '150ms ease',
    normal: '250ms ease',
    slow: '400ms ease',
  },
};

export type Theme = typeof theme;
