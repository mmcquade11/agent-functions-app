import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";

const LoginPage = () => {
  const { loginWithRedirect, isAuthenticated, isLoading } = useAuth0();

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      // Already logged in — send to where they came from or default to dashboard
      const lastPath = sessionStorage.getItem("postLoginRedirect") || "/dashboard";
      window.location.href = lastPath;
    }
  }, [isAuthenticated, isLoading]);

  const handleLogin = () => {
    // Save current path for post-login return
    sessionStorage.setItem("postLoginRedirect", window.location.pathname);

    loginWithRedirect({
      appState: {
        returnTo: window.location.pathname,
      },
    });
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen">
      <h1 className="text-3xl mb-6">Welcome</h1>
      <button
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        onClick={handleLogin}
      >
        Log In
      </button>
    </div>
  );
};

export default LoginPage;
