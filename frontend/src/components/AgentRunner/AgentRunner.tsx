import { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useAgentWebSocket } from "@/hooks/useAgentWebSocket";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Editor from "@monaco-editor/react";

export function AgentRunner() {
  const { getAccessTokenSilently } = useAuth0();

  const [userPrompt, setUserPrompt] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null);
  const [finalCode, setFinalCode] = useState<string>("");
  const [runLogs, setRunLogs] = useState<string[]>([]);

  const { messages, isStreaming } = useAgentWebSocket(submittedPrompt);

  const handleSubmit = () => {
    setSubmittedPrompt(userPrompt);
    setFinalCode("");
    setRunLogs([]);
  };

  const lastCodeChunk = messages.findLast((m) => m.type === "text" && m.phase === "claude");
  const hasEditor = lastCodeChunk && !finalCode;

  const handleRunNow = async () => {
    setRunLogs([]);
    const token = await getAccessTokenSilently();

    const res = await fetch("http://localhost:8000/api/v1/agents/execute", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ prompt: submittedPrompt, code: finalCode }),
    });

    if (!res.ok) {
      const err = await res.text();
      console.error("Run failed:", err);
      setRunLogs((prev) => [...prev, `[error] ${err}`]);
      return;
    }

    const reader = res.body?.getReader();
    const decoder = new TextDecoder();

    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        setRunLogs((prev) => [...prev, chunk]);
      }
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Prompt Input */}
      <Card>
        <CardContent className="space-y-4 p-4">
          <Textarea
            placeholder="Enter a prompt to create an agent..."
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
          />
          <Button onClick={handleSubmit} disabled={isStreaming}>
            {isStreaming ? "Streaming..." : "Create Agent"}
          </Button>
        </CardContent>
      </Card>

      {/* Agent Response Stream */}
      {messages.map((msg, idx) => (
        <Card key={idx}>
          <CardContent className="p-4 space-y-2">
            <p className="text-xs text-muted-foreground font-mono">
              [{msg.phase}] {msg.type}
            </p>
            {msg.content && (
              <pre className="bg-muted rounded p-2 whitespace-pre-wrap text-sm">
                {msg.content}
              </pre>
            )}
            {msg.tool && (
              <p className="text-sm">
                🔧 Tool: <strong>{msg.tool}</strong>
              </p>
            )}
            {msg.input && (
              <pre className="text-xs bg-gray-100 rounded p-2">
                {JSON.stringify(msg.input, null, 2)}
              </pre>
            )}
            {msg.result && (
              <pre className="text-xs bg-green-100 rounded p-2">
                {JSON.stringify(msg.result, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      ))}

      {/* Editable Final Code */}
      {(hasEditor || finalCode) && (
        <Card>
          <CardContent className="p-4 space-y-4">
            <div className="text-xs text-muted-foreground font-mono">Generated Code</div>
            <Editor
              height="400px"
              language="python"
              defaultValue={lastCodeChunk?.content ?? ""}
              value={finalCode || lastCodeChunk?.content || ""}
              onChange={(value) => setFinalCode(value || "")}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
              }}
            />

            <div className="flex gap-3 pt-2">
              <Button variant="default" onClick={handleRunNow}>
                🚀 Run Now
              </Button>
              <Button variant="secondary" onClick={() => console.log("SAVE", finalCode)}>
                💾 Save Draft
              </Button>
              <Button variant="outline" onClick={() => console.log("SCHEDULE", finalCode)}>
                ⏰ Schedule
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Run Output */}
      {runLogs.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="text-xs text-muted-foreground font-mono">Execution Output</div>
            {runLogs.map((line, idx) => (
              <pre key={idx} className="text-sm whitespace-pre-wrap">{line}</pre>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
