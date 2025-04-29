// src/pages/LoginPage.jsx

import { useAuth0 } from "@auth0/auth0-react";

const LoginPage = () => {
  const { loginWithRedirect, isAuthenticated } = useAuth0();

  if (isAuthenticated) {
    window.location.href = "/dashboard";
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen">
      <h1 className="text-3xl mb-6">Welcome</h1>
      <button
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        onClick={() => loginWithRedirect()}
      >
        Log In
      </button>
    </div>
  );
};

export default LoginPage;
