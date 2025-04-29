import { Link } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";

const Navbar = () => {
  const { logout, user } = useAuth0();

  const handleLogout = () => {
    logout({ returnTo: window.location.origin });
  };

  return (
    <nav className="bg-gray-800 p-4 text-white flex justify-between items-center">
      <div className="flex items-center space-x-6">
        <Link to="/dashboard" className="hover:text-gray-300">
          Dashboard
        </Link>
        <Link to="/workflows" className="hover:text-gray-300">
          Workflows
        </Link>
        <Link to="/executions" className="hover:text-gray-300">
          Executions
        </Link>
        <Link to="/prompt-entry" className="hover:text-gray-300">
          Prompt Entry
        </Link>
      </div>
      <div className="flex items-center space-x-4">
        {user && (
          <span className="text-sm text-gray-300">
            {user.name || user.email}
          </span>
        )}
        <button
          onClick={handleLogout}
          className="bg-red-500 hover:bg-red-600 px-3 py-1 rounded text-sm"
        >
          Logout
        </button>
      </div>
    </nav>
  );
};

export default Navbar;
