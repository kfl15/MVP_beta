import React from "react";
import App from "../App.jsx";
import { THEME } from "../theme";

export default function ProtectedApp({ onLogout }) {
  return (
    <div style={{ position: "relative", minHeight: "100vh" }}>
      <App />
      <button onClick={onLogout} title="Logout" style={styles.logoutBtn}>
        LogOut
      </button>
    </div>
  );
}

const styles = {
  logoutBtn: {
    position: "absolute",
    left: 18,
    bottom: 18,
    padding: "10px 14px",
    borderRadius: 12,
    background: THEME.logoutBg,
    color: THEME.logoutText,
    border: `1px solid ${THEME.logoutBorder}`,
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 700,
  },
};
