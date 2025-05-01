// frontend/src/components/AgentRunner/AgentRunner.tsx

import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Editor from "@monaco-editor/react";
import { useAgentWebSocket } from "@/hooks/useAgentWebSocket";
import { routeAndPreparePrompt } from "@/hooks/usePromptPlanner";

export function AgentRunner() {
  const [userPrompt, setUserPrompt] = useState("");
  const [finalCode, setFinalCode] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null);
  const [streamKey, setStreamKey] = useState(0);

  const { messages, isStreaming } = useAgentWebSocket(submittedPrompt);

  const handleSubmit = async () => {
    try {
      const { preparedPrompt } = await routeAndPreparePrompt(userPrompt);
      setFinalCode("");
      setSubmittedPrompt(preparedPrompt);
      setStreamKey((prev) => prev + 1); // force refresh websocket
    } catch (err) {
      console.error("Prompt processing failed:", err);
    }
  };

  const lastCodeChunk = messages.findLast((m) => m.type === "text" && m.phase === "claude");
  const hasEditor = lastCodeChunk && !finalCode;

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

      {/* Editable Final Code Block */}
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
              <Button variant="default" onClick={() => console.log("EXECUTE", finalCode)}>
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
    </div>
  );
}
