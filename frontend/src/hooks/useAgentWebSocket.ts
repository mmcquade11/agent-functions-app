import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useToast } from '@/hooks/use-toast';

type MessageProcessor = (message: any) => void;

export function useAgentWebSocket(prompt: string | null, processMessage: MessageProcessor) {
  const { getAccessTokenSilently } = useAuth0();
  const { toast } = useToast();
  const [messages, setMessages] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [connectionAttempts, setConnectionAttempts] = useState<number>(0);
  
  // References for WebSocket control
  const ws = useRef<WebSocket | null>(null);
  const isPaused = useRef<boolean>(false);
  const queuedMessages = useRef<any[]>([]);
  const maxReconnectAttempts = 3;

  // Create a clean-up function
  const cleanUp = useCallback(() => {
    if (ws.current) {
      if (ws.current.readyState === WebSocket.OPEN) {
        ws.current.close();
      }
      ws.current = null;
    }
    setIsConnected(false);
    setIsStreaming(false);
    isPaused.current = false;
    queuedMessages.current = [];
  }, []);

  // Function to pause the stream processing
  const pauseStream = useCallback(() => {
    console.log("Pausing WebSocket stream processing");
    isPaused.current = true;
  }, []);

  // Function to resume the stream processing
  const resumeStream = useCallback(() => {
    console.log("Resuming WebSocket stream processing");
    isPaused.current = false;
    
    // Process any queued messages
    if (queuedMessages.current.length > 0) {
      console.log(`Processing ${queuedMessages.current.length} queued messages`);
      queuedMessages.current.forEach(msg => {
        processMessage(msg);
        setMessages(prev => [...prev, msg]);
      });
      queuedMessages.current = [];
    }
  }, [processMessage]);

  // Effect to establish WebSocket connection
  useEffect(() => {
    if (!prompt) return;

    const connectWebSocket = async () => {
      try {
        cleanUp();
        setMessages([]);
        setError(null);
        setConnectionAttempts(prev => prev + 1);
        
        // Get fresh token
        const token = await getAccessTokenSilently({
          detailedResponse: true,
          cacheMode: 'no-cache' // Avoid using cached tokens
        }).then(resp => resp.access_token);
        
        if (!token) {
          throw new Error("Failed to get authentication token");
        }
        
        // Create WebSocket connection with token
        const socketUrl = `ws://localhost:8000/execute-agent?token=${token}`;
        console.log(`Connecting to WebSocket at ${socketUrl.substring(0, 50)}...`);
        
        ws.current = new WebSocket(socketUrl);
        
        // Set connection timeout
        const connectionTimeout = setTimeout(() => {
          if (ws.current && ws.current.readyState !== WebSocket.OPEN) {
            console.error("WebSocket connection timeout");
            ws.current.close();
            setError("Connection timed out. Please try again.");
            
            // Try to reconnect if within limits
            if (connectionAttempts < maxReconnectAttempts) {
              console.log(`Attempting to reconnect (${connectionAttempts + 1}/${maxReconnectAttempts})...`);
              connectWebSocket();
            } else {
              toast({
                title: "Connection failed",
                description: "Could not connect to the server after multiple attempts.",
                variant: "destructive",
              });
            }
          }
        }, 10000); // 10-second timeout
        
        ws.current.onopen = () => {
          console.log("WebSocket connection established");
          clearTimeout(connectionTimeout);
          setIsConnected(true);
          setError(null);
          
          // Send the prompt to the server
          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            const needsReasoning = sessionStorage.getItem('needsReasoning') === 'true';
            const payload = JSON.stringify({
              prompt,
              needsReasoning
            });
            console.log(`Sending payload to WebSocket: ${payload.substring(0, 100)}...`);
            ws.current.send(payload);
            setIsStreaming(true);
          }
        };
        
        ws.current.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            console.log("WebSocket message received:", message);
            
            // Handle various message types
            if (message.type === "done") {
              console.log("Stream complete");
              setIsStreaming(false);
            } else if (message.type === "error") {
              console.error("Error from server:", message.content);
              setError(message.content || "An error occurred");
              toast({
                title: "Server error",
                description: message.content || "An error occurred while processing your request.",
                variant: "destructive",
              });
              setIsStreaming(false);
            } else {
              // If paused, queue the message, otherwise process it
              if (isPaused.current) {
                console.log("Stream paused, queuing message");
                queuedMessages.current.push(message);
              } else {
                processMessage(message);
                setMessages(prev => [...prev, message]);
              }
            }
          } catch (e) {
            console.error("Error parsing WebSocket message:", e);
            setError("Error parsing message from server");
          }
        };
        
        ws.current.onerror = (event) => {
          console.error("WebSocket error:", event);
          setError("WebSocket connection error. The server might be unavailable.");
          setIsStreaming(false);
          
          toast({
            title: "Connection error",
            description: "There was a problem with the connection. Please try again.",
            variant: "destructive",
          });
        };
        
        ws.current.onclose = (event) => {
          clearTimeout(connectionTimeout);
          console.log(`WebSocket connection closed: ${event.code} - ${event.reason}`);
          setIsConnected(false);
          setIsStreaming(false);
          
          // Check if this was a clean close or an error
          if (event.code !== 1000) {
            console.error(`WebSocket closed with code ${event.code}`);
            setError(`Connection closed: ${event.reason || "Unknown reason"}`);
            
            // Only show toast for unexpected closures
            if (!error) {
              toast({
                title: "Connection closed",
                description: "The connection was closed unexpectedly. Try refreshing the page.",
                variant: "default",
              });
            }
          }
        };
        
      } catch (err) {
        console.error("Error setting up WebSocket:", err);
        setError(`Failed to connect: ${err.message}`);
        toast({
          title: "Connection failed",
          description: `Could not establish connection: ${err.message}`,
          variant: "destructive",
        });
      }
    };

    connectWebSocket();
    
    // Clean up on unmount
    return () => {
      cleanUp();
    };
  }, [prompt, getAccessTokenSilently, cleanUp, processMessage, connectionAttempts, toast]);

  // Reconnect with a different prompt
  const reconnect = useCallback(async (newPrompt: string) => {
    if (!newPrompt) return;
    
    try {
      cleanUp();
      setMessages([]);
      setConnectionAttempts(0);
      
      // Get fresh token
      const token = await getAccessTokenSilently({
        detailedResponse: true,
        cacheMode: 'no-cache'
      }).then(resp => resp.access_token);
      
      // Create WebSocket connection with token
      const socketUrl = `ws://localhost:8000/execute-agent?token=${token}`;
      ws.current = new WebSocket(socketUrl);
      
      // Set connection timeout
      const connectionTimeout = setTimeout(() => {
        if (ws.current && ws.current.readyState !== WebSocket.OPEN) {
          console.error("WebSocket connection timeout during reconnect");
          ws.current.close();
          setError("Connection timed out during reconnect. Please try again.");
        }
      }, 10000);
      
      ws.current.onopen = () => {
        console.log("WebSocket reconnection established");
        clearTimeout(connectionTimeout);
        setIsConnected(true);
        
        // Send the new prompt to the server
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
          const needsReasoning = sessionStorage.getItem('needsReasoning') === 'true';
          ws.current.send(JSON.stringify({
            prompt: newPrompt,
            needsReasoning
          }));
          setIsStreaming(true);
        }
      };
      
      // Set up the same event handlers as in the useEffect
      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === "done") {
            setIsStreaming(false);
          } else if (message.type === "error") {
            console.error("Error from server during reconnect:", message.content);
            setError(message.content || "An error occurred");
            setIsStreaming(false);
          } else {
            if (isPaused.current) {
              queuedMessages.current.push(message);
            } else {
              processMessage(message);
              setMessages(prev => [...prev, message]);
            }
          }
        } catch (e) {
          console.error("Error parsing WebSocket message:", e);
          setError("Error parsing message from server");
        }
      };
      
      ws.current.onerror = (event) => {
        clearTimeout(connectionTimeout);
        console.error("WebSocket reconnection error:", event);
        setError("WebSocket reconnection error");
        setIsStreaming(false);
      };
      
      ws.current.onclose = (event) => {
        clearTimeout(connectionTimeout);
        console.log("WebSocket reconnection closed");
        setIsConnected(false);
        setIsStreaming(false);
      };
      
    } catch (err) {
      console.error("Error during WebSocket reconnection:", err);
      setError(`Failed to reconnect: ${err.message}`);
    }
  }, [getAccessTokenSilently, cleanUp, processMessage]);

  return {
    messages,
    isConnected,
    isStreaming,
    error,
    pauseStream,
    resumeStream,
    reconnect
  };
}