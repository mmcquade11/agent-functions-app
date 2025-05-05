import { useEffect, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import AgentEditModal from "@/components/AgentEditModal";

type Agent = {
  id: string;
  name: string;
  description: string;
  status: string;
  prompt_id: string;
  agent_code: string;
};

export default function AgentDashboard() {
  const { getAccessTokenSilently } = useAuth0();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

  const fetchAgents = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getAccessTokenSilently();
      const res = await fetch("http://localhost:8000/api/v1/agents", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to fetch agents");
      const data = await res.json();
      setAgents(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (agentId: string) => {
    const token = await getAccessTokenSilently();
    const res = await fetch(`http://localhost:8000/api/v1/agents/${agentId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      setAgents((prev) => prev.filter((a) => a.id !== agentId));
    }
  };

  const handleSave = (updated: Agent) => {
    setAgents((prev) =>
      prev.map((a) => (a.id === updated.id ? updated : a))
    );
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">🧠 Your Agents</h1>

      {loading && <p>Loading agents...</p>}
      {error && <p className="text-red-600">{error}</p>}
      {agents.length === 0 && !loading && (
        <p className="text-muted-foreground">No agents yet.</p>
      )}

      {agents.map((agent) => (
        <Card key={agent.id}>
          <CardHeader>
            <CardTitle>{agent.name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-muted-foreground">{agent.description}</p>
            <pre className="bg-gray-100 text-sm rounded p-2 overflow-x-auto">
              {agent.agent_code}
            </pre>
            <div className="flex gap-3 pt-2">
              <Button variant="outline" onClick={() => setEditingAgent(agent)}>
                ✏️ Edit
              </Button>
              <Button
                variant="destructive"
                onClick={() => handleDelete(agent.id)}
              >
                🗑 Delete
              </Button>
              <Button onClick={() => console.log("RUN", agent)}>🚀 Run</Button>
              <Button variant="secondary" onClick={() => console.log("TEST", agent)}>
                🧪 Test
              </Button>
              <Button variant="ghost" onClick={() => console.log("SCHEDULE", agent)}>
                ⏰ Schedule
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}

      {editingAgent && (
        <AgentEditModal
          open={!!editingAgent}
          agent={editingAgent}
          onClose={() => setEditingAgent(null)}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
