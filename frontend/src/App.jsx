import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useEffect, useRef, useState } from "react";

// Pages
import DashboardPage from "./pages/DashboardPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import ExecutionsPage from "./pages/ExecutionsPage";
import ExecutionDetailPage from "./pages/ExecutionDetailPage";
import PromptEntryPage from "./pages/PromptEntryPage";
import CreateAgentPage from "./pages/agents/CreateAgentPage";
import LoginPage from "./pages/LoginPage";

function App() {
  const {
    isLoading,
    isAuthenticated,
    handleRedirectCallback,
  } = useAuth0();
  
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
          const returnTo = result?.appState?.returnTo || "/dashboard";
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
      <Route path="/" element={!isAuthenticated ? <LoginPage /> : <Navigate to="/dashboard" />} />
      <Route
        path="/dashboard"
        element={isAuthenticated ? <DashboardPage /> : <Navigate to="/" />}
      />
      <Route
        path="/workflows"
        element={isAuthenticated ? <WorkflowsPage /> : <Navigate to="/" />}
      />
      <Route
        path="/executions"
        element={isAuthenticated ? <ExecutionsPage /> : <Navigate to="/" />}
      />
      <Route
        path="/executions/:id"
        element={isAuthenticated ? <ExecutionDetailPage /> : <Navigate to="/" />}
      />
      <Route
        path="/prompt-entry"
        element={isAuthenticated ? <PromptEntryPage /> : <Navigate to="/" />}
      />
      <Route
        path="/agents/create"
        element={isAuthenticated ? <CreateAgentPage /> : <Navigate to="/" />}
      />
    </Routes>
  );
}

export default App;
