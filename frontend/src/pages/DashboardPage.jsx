import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";

const DashboardPage = () => {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(false);
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-lg">Loading...</p>
      </div>
    );
  }

  return (
    <div>
      <Navbar />
      <div className="p-8">
        <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
        <p className="text-gray-600">Welcome to your dashboard.</p>
      </div>
    </div>
  );
};

export default DashboardPage;
