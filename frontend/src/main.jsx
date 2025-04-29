// src/main.jsx

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AuthProvider from "./auth/AuthProvider";
import { useAuth0 } from "@auth0/auth0-react";
import { setAuthFunctions } from "./api/axios";
import ProtectedRoute from "./auth/ProtectedRoute";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import ExecutionsPage from "./pages/ExecutionsPage";
import ExecutionDetailPage from "./pages/ExecutionDetailPage";
import PromptEntryPage from "./pages/PromptEntryPage";

import "./index.css";

const App = () => {
  const auth0 = useAuth0();

  React.useEffect(() => {
    const silentlyAuthenticate = async () => {
      try {
        if (!auth0.isAuthenticated && !auth0.isLoading) {
          await auth0.getAccessTokenSilently();
        }
        setAuthFunctions(auth0);
      } catch (error) {
        console.error("Silent auth failed", error);
      }
    };
    silentlyAuthenticate();
  }, [auth0.isAuthenticated, auth0.isLoading]); // important deps!

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workflows"
        element={
          <ProtectedRoute>
            <WorkflowsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/executions"
        element={
          <ProtectedRoute>
            <ExecutionsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/executions/:executionId"
        element={
          <ProtectedRoute>
            <ExecutionDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/prompt-entry"
        element={
          <ProtectedRoute>
            <PromptEntryPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<LoginPage />} />
    </Routes>
  );
};

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
);
