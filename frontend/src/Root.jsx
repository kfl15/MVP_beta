import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage.jsx";
import ProtectedApp from "./pages/ProtectedApp.jsx";

const LS_KEY = "kfl15_auth";

export default function Root() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) setUser(JSON.parse(raw));
  }, []);

  const login = (u) => {
    localStorage.setItem(LS_KEY, JSON.stringify(u));
    setUser(u);
  };

  const logout = () => {
    localStorage.removeItem(LS_KEY);
    setUser(null);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={user ? <Navigate to="/" replace /> : <LoginPage onSuccess={login} />}
        />
        <Route
          path="/"
          element={user ? <ProtectedApp onLogout={logout} /> : <Navigate to="/login" replace />}
        />
        <Route path="*" element={<Navigate to={user ? "/" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
