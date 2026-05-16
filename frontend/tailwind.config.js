/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        paper: "rgb(var(--color-paper) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        "surface-muted": "rgb(var(--color-surface-muted) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        "ink-soft": "rgb(var(--color-ink-soft) / <alpha-value>)",
        "ink-faint": "rgb(var(--color-ink-faint) / <alpha-value>)",
        rule: "rgb(var(--color-rule) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        "accent-soft": "rgb(var(--color-accent-soft) / <alpha-value>)",
        solved: "rgb(var(--color-solved) / <alpha-value>)",
        hint: "rgb(var(--color-hint) / <alpha-value>)",
        calibrate: "rgb(var(--color-calibrate) / <alpha-value>)",
        alarm: "rgb(var(--color-alarm) / <alpha-value>)",
      },
      fontFamily: {
        display: ['"Fraunces Variable"', "Fraunces", "ui-serif", "Georgia", "serif"],
        body: ['"Inter Variable"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', '"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        display: ["clamp(2rem, 4vw, 3rem)", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        "serif-lede": ["1.125rem", { lineHeight: "1.5" }],
        body: ["0.9375rem", { lineHeight: "1.55" }],
        "body-emphasis": ["0.9375rem", { lineHeight: "1.55", fontWeight: "500" }],
        label: ["0.6875rem", { lineHeight: "1.2", letterSpacing: "0.12em", fontWeight: "500" }],
        caption: ["0.8125rem", { lineHeight: "1.4" }],
        mono: ["0.8125rem", { lineHeight: "1.4" }],
      },
      borderRadius: {
        md: "6px",
        lg: "8px",
        xl: "14px",
      },
      transitionTimingFunction: {
        soft: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
