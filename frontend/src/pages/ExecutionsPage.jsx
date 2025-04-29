// src/pages/ExecutionsPage.jsx

import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";

const ExecutionsPage = () => {
  const [loading, setLoading] = useState(true);
  

  useEffect(() => {
    // Placeholder for fetching executions
    const fetchExecutions = async () => {
      setLoading(false);
    };
    fetchExecutions();
  }, []);

  if (loading) {
    return (
      <div>
        <Navbar /> {/* ✅ Always show Navbar */}
        <div className="flex items-center justify-center h-screen">
          <p className="text-lg">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Navbar /> {/* ✅ Always show Navbar */}
      <div className="p-8">
        <h1 className="text-3xl font-bold mb-6">Executions</h1>
        <p className="text-gray-600">View and manage your executuiions here....</p>
      </div>
    </div>
  );
};

export default ExecutionsPage;
