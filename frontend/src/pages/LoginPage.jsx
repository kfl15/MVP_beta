import React, { useState } from "react";
import { THEME } from "../theme";

const ALLOWED_USERS = {
  "admin1@gmail.com": "admin1@12",
  "admin2@gmail.com": "admin2@12",
};

const BRAND = {
  logoSrc: "/logo.png", // put logo in frontend/public/logo.png
  title: "FinVault AI",
  motto: "Private AI for Accounting Documents.",
  sub: "Your documents are processed only within your firm and are never used to train AI models.",
};

export default function LoginPage({ onSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setErr("");

    const eNorm = email.trim().toLowerCase();
    const pNorm = password.trim();

    if (!eNorm || !pNorm) {
      setErr("Enter email and password.");
      return;
    }

    const expectedPassword = ALLOWED_USERS[eNorm];
    if (!expectedPassword) {
      setErr("Invalid email.");
      return;
    }

    if (pNorm !== expectedPassword) {
      setErr("Invalid password.");
      return;
    }

    onSuccess({ email: eNorm });
  };

  return (
    <div style={styles.page}>
      {/* LEFT PANEL — LOGIN */}
      <div style={styles.leftPanel}>
        <div style={styles.card}>
          <div style={styles.title}>Login</div>

          <form onSubmit={handleSubmit} style={styles.form}>
            <label style={styles.label}>Email</label>
            <input
              style={styles.input}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your_ID@gmail.com"
            />

            <label style={styles.label}>Password</label>
            <input
              style={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              placeholder="••••••••"
            />

            {err && <div style={styles.error}>{err}</div>}

            <button type="submit" style={styles.button}>
              Sign in
            </button>
          </form>

          <div style={styles.hint}>
            FinVaultAI runs privately & does NOT use customer data to train AI models.
          </div>
        </div>
      </div>

      {/* RIGHT PANEL — BRANDING */}
      <div style={styles.rightPanel}>
        <div style={styles.brandCard}>
          <img src={BRAND.logoSrc} alt="FinVault AI" style={styles.logo} />
          <div style={styles.brandTitle}>{BRAND.title}</div>
          <div style={styles.brandMotto}>{BRAND.motto}</div>
          <div style={styles.brandSub}>{BRAND.sub}</div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    width: "100%",
    display: "flex",
    background: THEME.loginPageBg,
    color: THEME.loginText,
  },

  leftPanel: {
    flex: "0 0 420px",
    minWidth: 320,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },

  rightPanel: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    background: THEME.loginRightPanelBg,
    borderLeft: `1px solid ${THEME.loginBorder}`,
  },

  card: {
    width: "100%",
    maxWidth: 360,
    background: THEME.loginLeftCardBg,
    border: `1px solid ${THEME.loginBorder}`,
    borderRadius: 16,
    padding: 24,
    boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
  },

  title: {
    fontSize: 22,
    fontWeight: 700,
    marginBottom: 16,
  },

  form: {
    display: "grid",
    gap: 10,
  },

  label: {
    fontSize: 13,
    fontWeight: 600,
  },

  input: {
    padding: "10px 12px",
    borderRadius: 10,
    border: `1px solid ${THEME.loginBorder}`,
    background: "#FFFFFF",
    color: THEME.loginText,
    outline: "none",
  },

  error: {
    background: THEME.loginDangerBg,
    border: `1px solid ${THEME.loginDangerBorder}`,
    color: THEME.loginDangerText,
    padding: "8px 10px",
    borderRadius: 10,
    fontSize: 13,
  },

  button: {
    marginTop: 8,
    padding: "10px 12px",
    borderRadius: 10,
    border: "none",
    background: THEME.loginAccent,
    color: "#FFFFFF",
    fontWeight: 700,
    cursor: "pointer",
  },

  hint: {
    marginTop: 14,
    fontSize: 12,
    color: THEME.loginMuted,
  },

  brandCard: {
    width: "100%",
    maxWidth: 520,
    background: "#FFFFFF",
    border: `1px solid ${THEME.loginBorder}`,
    borderRadius: 18,
    padding: 28,
    boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
  },

  logo: {
    width: 150,
    marginBottom: 16,
  },

  brandTitle: {
    fontSize: 26,
    fontWeight: 800,
    marginBottom: 10,
  },

  brandMotto: {
    fontSize: 16,
    fontWeight: 600,
    marginBottom: 8,
  },

  brandSub: {
    fontSize: 14,
    color: THEME.loginMuted,
    lineHeight: 1.6,
  },
};
