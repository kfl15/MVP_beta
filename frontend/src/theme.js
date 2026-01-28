// frontend/src/theme.js
export const THEME = {
  /* ===== Buyer Light / Teal Theme ===== */

  // Layout
  pageBg: "#F6FBFB",

  // Sidebar
  sidebarBg: "#0F4C5C",
  sidebarText: "#FFFFFF",
  sidebarCardBg: "rgba(255,255,255,0.08)",

  // Main area
  mainBg: "#E0F2FE",
  cardBg: "#FFFFFF",

  // Chat bubbles
  userBubbleBg: "#0F4C5C",
  userBubbleText: "#FFFFFF",
  botBubbleBg: "#FFFFFF",
  botBubbleText: "#0F172A",

  // Borders / dividers
  divider: "#E2EEEE",
  inputBorder: "#CBD5E1",

  // Inputs
  inputBg: "#FFFFFF",
  inputText: "#000000",

  // Buttons
  primaryBtnBg: "#0F4C5C",
  primaryBtnText: "#FFFFFF",

  danger: "#B91C1C",

  // Muted text
  mutedText: "#475569",

  /* ===== Login Page (keep stable) =====
     IMPORTANT:
     - LoginPage.jsx uses the keys below (loginPageBg, loginLeftCardBg, etc.)
     - The extra "loginBg/loginCardBg/..." aliases are kept for backward safety
  */

  // Legacy login aliases (safe to keep)
  loginBg: "#F6FBFB",            // same as loginPageBg
  loginCardBg: "#FFFFFF",        // same as loginLeftCardBg
  loginSideBg: "#D9F2F2",        // same as loginRightPanelBg
  loginCardBorder: "#E2EEEE",    // same as loginBorder

  loginBtnBg: "#0F4C5C",         // same as loginAccent
  loginBtnHover: "#0C3E4B",
  loginBtnText: "#FFFFFF",

  loginInputBg: "#FFFFFF",
  loginInputBorder: "#94a3b8",
  loginInputText: "#0F172A",

  loginTitleText: "#0F172A",
  loginBodyText: "#0F172A",
  loginMutedText: "#475569",

  // LoginPage.jsx keys (REQUIRED)
  loginPageBg: "#F6FBFB",
  loginLeftCardBg: "#FFFFFF",
  loginRightPanelBg: "#D9F2F2",
  loginBorder: "#E2EEEE",

  loginAccent: "#0F4C5C",
  loginAccentHover: "#0C3E4B",

  loginText: "#0F172A",
  loginMuted: "#475569",

  loginDangerBg: "#FEE2E2",
  loginDangerBorder: "#FECACA",
  loginDangerText: "#B91C1C",
};
