import React, { useState } from "react";

export default function LoginPage({ onSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setErr("");

    // UI-only login for now (no backend changes).
    if (email.trim().length < 3 || password.trim().length < 3) {
      setErr("Enter a valid email and password.");
      return;
    }

    onSuccess({ email });
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.title}>Login</div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>Email</label>
          <input
            style={styles.input}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            autoComplete="username"
          />

          <label style={styles.label}>Password</label>
          <input
            style={styles.input}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            type="password"
            autoComplete="current-password"
          />

          {err ? <div style={styles.error}>{err}</div> : null}

          <button type="submit" style={styles.button}>
            Sign in
          </button>
        </form>

        <div style={styles.hint}>
          (UI-only login for now. We can connect real auth later.)
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    background: "#0b1220",
    padding: 24,
  },
  card: {
    width: 360,
    background: "#111a2e",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 16,
    padding: 20,
    color: "white",
    boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
  },
  title: { fontSize: 20, fontWeight: 700, marginBottom: 12 },
  form: { display: "grid", gap: 10 },
  label: { fontSize: 13, opacity: 0.9 },
  input: {
    padding: "10px 12px",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.10)",
    background: "#0c1426",
    color: "white",
    outline: "none",
  },
  error: {
    background: "rgba(255, 80, 80, 0.12)",
    border: "1px solid rgba(255, 80, 80, 0.25)",
    padding: "8px 10px",
    borderRadius: 10,
    color: "#ffb4b4",
    fontSize: 13,
  },
  button: {
    marginTop: 6,
    padding: "10px 12px",
    borderRadius: 10,
    border: "none",
    background: "#4f7cff",
    color: "white",
    fontWeight: 700,
    cursor: "pointer",
  },
  hint: { marginTop: 12, fontSize: 12, opacity: 0.7 },
};
