import { useState } from "react";
import Navbar from "../components/Navbar";
import { optimizePrompt, routePrompt } from "../api/prompt";

const PromptEntryPage = () => {
  const [prompt, setPrompt] = useState("");
  const [optimizedPrompt, setOptimizedPrompt] = useState("");
  const [needsReasoning, setNeedsReasoning] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setNeedsReasoning(null);

    try {
      const optimized = await optimizePrompt(prompt);
      setOptimizedPrompt(optimized.optimized_prompt);

      const routing = await routePrompt(optimized.optimized_prompt);
      setNeedsReasoning(routing.needs_reasoning);
    } catch (err) {
      setError("Failed to optimize or route prompt.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Navbar />
      <div className="p-8">
        <h1 className="text-3xl font-bold mb-6">Prompt Entry</h1>

        <form onSubmit={handleSubmit} className="flex flex-col space-y-4">
          <textarea
            className="w-full border border-gray-300 p-3 rounded-lg"
            rows="4"
            placeholder="Enter your prompt here..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Processing..." : "Optimize & Route Prompt"}
          </button>
        </form>

        {error && (
          <p className="text-red-500 mt-4">
            {error}
          </p>
        )}

        {optimizedPrompt && (
          <div className="mt-8">
            <h2 className="text-2xl font-bold mb-2">Optimized Prompt:</h2>
            <p className="bg-gray-100 p-4 rounded-lg">{optimizedPrompt}</p>

            {needsReasoning !== null && (
              <p className="mt-4 text-lg">
                <span className="font-bold">Needs Reasoning:</span> {needsReasoning ? "Yes" : "No"}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PromptEntryPage;
