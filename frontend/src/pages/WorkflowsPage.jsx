import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";

const WorkflowsPage = () => {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWorkflows = async () => {
      setLoading(false);
    };
    fetchWorkflows();
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
        <h1 className="text-3xl font-bold mb-6">Workflows</h1>
        <p className="text-gray-600">Manage your workflows here....</p>
      </div>
    </div>
  );
};

export default WorkflowsPage;
