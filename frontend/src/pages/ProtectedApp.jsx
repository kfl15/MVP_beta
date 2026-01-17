import React from "react";
import App from "../App.jsx";

export default function ProtectedApp({ onLogout }) {
  return (
    <div style={{ position: "relative", minHeight: "100vh" }}>
      <App />

      {/* Logout icon at left-panel bottom (overlay; App.jsx stays unchanged) */}
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

    background: "#ffffff",     // white background
    color: "#ff0000",          // red font
    border: "1px solid #000",  // black border

    cursor: "pointer",
    fontSize: 14,
    fontWeight: 700,
  },
};