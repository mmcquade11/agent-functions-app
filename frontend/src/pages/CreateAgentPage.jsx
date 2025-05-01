import { AgentRunner } from "@/components/AgentRunner/AgentRunner";

export default function CreateAgentPage() {
  return (
    <main className="p-6">
      <h1 className="text-xl font-bold mb-4">Create New Agent</h1>
      <AgentRunner />
    </main>
  );
}
