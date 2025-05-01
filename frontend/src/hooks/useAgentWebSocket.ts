import { useEffect, useRef, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

type StreamMessage = {
  phase: "reasoning" | "claude" | "done";
  type: "text" | "tool_use" | "tool_result" | "code" | "start" | "done";
  content?: string;
  tool?: string;
  input?: any;
  result?: any;
};

export function useAgentWebSocket(prompt: string | null) {
  const { getAccessTokenSilently } = useAuth0();
  const [messages, setMessages] = useState<StreamMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!prompt) return;

    let ws: WebSocket;

    (async () => {
      try {
        console.log("Getting access token...");
        const token = await getAccessTokenSilently();
        console.log("Token received:", token.substring(0, 10) + "...");

        // Try with query param instead of subprotocol
        const wsUrl = `ws://localhost:8000/ws/execute-agent?token=${encodeURIComponent(token)}`;
        console.log("Connecting to:", wsUrl);
        
        ws = new WebSocket(wsUrl);
        socketRef.current = ws;
        setMessages([]);
        setIsStreaming(true);

        ws.onopen = () => {
          console.log("WebSocket connection opened!");
          ws.send(JSON.stringify({ prompt }));
        };

        ws.onmessage = (event) => {
          console.log("Message received:", event.data.substring(0, 50) + "...");
          const data: StreamMessage = JSON.parse(event.data);
          setMessages((prev) => [...prev, data]);
          if (data.type === "done") {
            setIsStreaming(false);
          }
        };

        ws.onerror = (err) => {
          console.error("WebSocket error:", err);
          setIsStreaming(false);
        };

        ws.onclose = (event) => {
          console.log("WebSocket closed with code:", event.code, event.reason);
          setIsStreaming(false);
        };
      } catch (error) {
        console.error("Error setting up WebSocket:", error);
        setIsStreaming(false);
      }
    })();

    return () => {
      if (ws) {
        console.log("Cleanup: closing WebSocket");
        ws.close();
      }
    };
  }, [prompt]);

  return { messages, isStreaming };
}