// src/App.jsx
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useEffect, useRef, useState } from "react";

// Pages
import DashboardPage from "./pages/DashboardPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import ExecutionsPage from "./pages/ExecutionsPage";
import ExecutionDetailPage from "./pages/ExecutionDetailPage";
import PromptEntryPage from "./pages/PromptEntryPage";
import CreateAgentPage from "./pages/agents/CreateAgentPage";
import DashboardAgentsPage from "./pages/agents/DashboardAgents";
import LoginPage from "./pages/LoginPage";

function App() {
  const { isLoading, isAuthenticated, handleRedirectCallback } = useAuth0();

  const hasHandledRedirect = useRef(false);
  const [redirectHandled, setRedirectHandled] = useState(false);

  useEffect(() => {
    const runRedirectHandler = async () => {
      if (
        window.location.search.includes("code=") &&
        window.location.search.includes("state=") &&
        !hasHandledRedirect.current
      ) {
        hasHandledRedirect.current = true;
        try {
          const result = await handleRedirectCallback();
          const returnTo = result?.appState?.returnTo || "/agents";
          window.history.replaceState({}, document.title, returnTo);
          setRedirectHandled(true);
        } catch (err) {
          console.error("❌ Auth0 redirect error:", err);
        }
      } else {
        setRedirectHandled(true);
      }
    };

    runRedirectHandler();
  }, []);

  if (isLoading || !redirectHandled) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <Routes>
      <Route path="/" element={!isAuthenticated ? <LoginPage /> : <Navigate to="/agents" />} />
      <Route path="/login" element={<LoginPage />} />

      {isAuthenticated && (
        <>
          <Route path="/dashboard" element={<Navigate to="/agents" replace />} />
          <Route path="/agents" element={<DashboardAgentsPage />} />
          <Route path="/agents/create" element={<CreateAgentPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/executions" element={<ExecutionsPage />} />
          <Route path="/executions/:id" element={<ExecutionDetailPage />} />
          <Route path="/prompt-entry" element={<PromptEntryPage />} />
        </>
      )}

      {!isAuthenticated && (
        <Route path="*" element={<Navigate to="/login" replace />} />
      )}
    </Routes>
  );
}

export default App;
