export const harborTokens = {
  name: "Harbor",
  description: "Warm, data-forward design system extracted from the Household Portfolio Tracker.",
  fonts: {
    body: "\"IBM Plex Sans\", sans-serif",
    display: "\"Space Grotesk\", sans-serif",
  },
  colors: {
    background: "#f8f5ef",
    panel: "rgba(255, 255, 255, 0.82)",
    panelStrong: "#ffffff",
    ink: "#102336",
    muted: "#546173",
    line: "rgba(16, 35, 54, 0.12)",
    accent: "#0b7fab",
    accentPositive: "#1f9f6f",
    accentWarm: "#ff7f50",
    accentGlow: "#ffcb77",
    danger: "#b23b3b",
  },
  spacing: {
    2: "8px",
    3: "12px",
    4: "16px",
    5: "20px",
    6: "24px",
    8: "32px",
    10: "40px",
  },
  radius: {
    sm: "14px",
    md: "20px",
    lg: "24px",
    pill: "999px",
  },
  shadow: {
    panel: "0 20px 40px rgba(16, 35, 54, 0.08)",
  },
  guidance: {
    backgroundStrategy: "Use the warm canvas for the page and reserve white/transparent glass surfaces for content.",
    headingStrategy: "Use display type sparingly for headlines, section titles, and numeric highlights.",
    actionStrategy: "Primary actions are blue pills, destructive actions are outlined red pills, and everything else stays neutral.",
  },
} as const;

export type HarborTokens = typeof harborTokens;
