// src/pages/ExecutionDetailPage.jsx

import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";

const ExecutionDetailPage = () => {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Placeholder for fetching a specific execution detail
    const fetchExecutionDetail = async () => {
      setLoading(false);
    };
    fetchExecutionDetail();
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
        <h1 className="text-3xl font-bold mb-6">Execution Detail</h1>
        <p className="text-gray-600">Detailed view of a single execution.</p>
      </div>
    </div>
  );
};

export default ExecutionDetailPage;
