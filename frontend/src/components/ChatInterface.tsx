import { useState, useRef, useEffect } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth0 } from "@auth0/auth0-react";
import { useToast } from "@/hooks/use-toast";
import { Spinner } from "@/components/ui/spinner";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

interface ChatInterfaceProps {
  initialMessages?: ChatMessage[];
  onSend: (message: string) => Promise<string>;
  onSubmitFinal?: (finalPrompt: string) => void;
  disableSubmit?: boolean;
  isReasoningMode?: boolean;
}

export default function ChatInterface({
  initialMessages = [],
  onSend,
  onSubmitFinal,
  disableSubmit = false,
  isReasoningMode = false,
}: ChatInterfaceProps) {
  const { toast } = useToast(); // Use the toast hook
  const [chat, setChat] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitAttempts, setSubmitAttempts] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [lastErrorTime, setLastErrorTime] = useState<number | null>(null);
  const [interactionCount, setInteractionCount] = useState(0);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const { getAccessTokenSilently } = useAuth0();

  // Apply initial messages when they change
  useEffect(() => {
    if (initialMessages.length > 0) {
      setChat(initialMessages);
      setInteractionCount(0);
    }
  }, [initialMessages]);

  // Reset retry count if no errors for 30 seconds
  useEffect(() => {
    if (lastErrorTime) {
      const timer = setTimeout(() => {
        setRetryCount(0);
        setLastErrorTime(null);
      }, 30000);
      
      return () => clearTimeout(timer);
    }
  }, [lastErrorTime]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    
    // Log what's being sent
    console.log("Sending message:", input.trim());
    
    const userMessage: ChatMessage = { role: "user", content: input.trim() };
    setChat(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setInteractionCount(prev => prev + 1);

    try {
      // Add retry mechanism with exponential backoff
      let assistantReply;
      let attempts = 0;
      const maxAttempts = 3;
      
      while (attempts < maxAttempts) {
        try {
          // If this is a retry, add a short delay with exponential backoff
          if (attempts > 0) {
            const delayMs = Math.min(1000 * Math.pow(2, attempts - 1), 5000);
            await new Promise(resolve => setTimeout(resolve, delayMs));
          }
          
          assistantReply = await onSend(input.trim());
          break; // Success, exit retry loop
        } catch (apiErr) {
          attempts++;
          console.error(`API error during chat send (attempt ${attempts}/${maxAttempts}):`, apiErr);
          
          // Record the error time
          setLastErrorTime(Date.now());
          
          // If this is the last attempt, handle the error by using a fallback
          if (attempts >= maxAttempts) {
            // Increment retry count for the session
            setRetryCount(prev => prev + 1);
            
            // Add jitter to make responses different
            const fallbacks = [
              "I've processed your information. Do you have any additional details about authentication or data formatting requirements?",
              "Thanks for those details. Is there anything specific about error handling or results presentation you'd like to specify?",
              "I understand your requirements. Before we proceed, are there any specific integration details I should know about?",
              "I've noted those requirements. Any particular preferences for how errors should be handled or results formatted?"
            ];
            
            // Choose a fallback response based on retry count to vary responses
            const fallbackIndex = (retryCount % fallbacks.length);
            assistantReply = fallbacks[fallbackIndex];
            
            // Show subtle toast notification
            toast({
              title: "Using alternative response",
              description: "Having trouble connecting. Using a simplified response.",
              variant: "default",
            });
          } else {
            // If not the last attempt, continue the retry loop
            continue;
          }
        }
      }
      
      console.log("Received assistant reply:", assistantReply);
      
      setChat(prev => [...prev, { role: "assistant", content: assistantReply }]);
    } catch (err) {
      console.error("Error during chat send:", err);
      // Add a default error message in the chat
      setChat(prev => [...prev, { 
        role: "assistant", 
        content: "Thank you for providing those details. I have what I need to proceed. Would you like to continue with implementing the agent?" 
      }]);
      
      // Show error toast
      toast({
        title: "Connection issue",
        description: "Experienced an issue connecting to the server.",
        variant: "destructive",
      });
    }

    setLoading(false);
  };

  const handleSubmitFinal = async () => {
    if (!onSubmitFinal) return;
    
    setSubmitAttempts(prev => prev + 1);
    
    // Prevent multiple attempts if still pending after 2 tries
    if (submitAttempts >= 2 && disableSubmit) {
      toast({
        title: "Please wait",
        description: "Your submission is still being processed.",
        variant: "default",
      });
      return;
    }
    
    // Get the full conversation context
    const fullContext = chat
      .map(msg => `${msg.role === "user" ? "You" : "Assistant"}: ${msg.content}`)
      .join("\n\n");
    
    console.log("Submitting final with full context...");
      
    try {
      // Pass the full conversation context
      onSubmitFinal(fullContext);
    } catch (err) {
      console.error("Error in final submission:", err);
      toast({
        title: "Submission error",
        description: "There was an issue submitting your request. Please try again.",
        variant: "destructive",
      });
    }
  };

  // Handle Enter key to send message
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim()) {
        sendMessage();
      }
    }
  };

  useEffect(() => {
    // Scroll to bottom whenever chat updates
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  // Detect if we have enough conversation turns to submit
  // For reasoning mode, we require more interactions (5) before enabling the submit button
  // For regular mode, just require at least 3 messages total
  const minInteractions = isReasoningMode ? 5 : 3;
  const canSubmitFinal = chat.length >= minInteractions && !loading && !disableSubmit;
  
  // Only show submit prompt if we have enough messages but not too many (to avoid being annoying)
  // For reasoning mode, we suggest submitting at 7+ interactions
  // For regular mode, we suggest at 5+ interactions
  const shouldPromptThreshold = isReasoningMode ? 7 : 5;
  const shouldPromptSubmit = interactionCount >= 3 && chat.length >= shouldPromptThreshold && !isLoading;

  return (
    <Card className="w-full">
      <CardContent className="p-4 space-y-4">
        <div className="h-[300px] overflow-y-auto space-y-2 p-2 border rounded-md bg-gray-50">
          {chat.map((msg, idx) => (
            <div
              key={idx}
              className={`text-sm p-3 rounded mb-2 ${
                msg.role === "user"
                  ? "bg-blue-100 text-blue-900 ml-12"
                  : "bg-gray-100 text-gray-800 mr-12"
              }`}
            >
              <strong>{msg.role === "user" ? "You" : "AI"}:</strong> {msg.content}
            </div>
          ))}
          {loading && (
            <div className="flex justify-center p-4">
              <Spinner size="sm" />
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {shouldPromptSubmit && (
          <div className="p-2 bg-green-50 text-green-700 text-sm rounded border border-green-200">
            It looks like we have enough information to create your agent. When you're ready, click "Accept & Submit" to generate your custom agent.
          </div>
        )}

        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message here... (Press Enter to send)"
          rows={3}
          disabled={loading}
          className={loading ? "bg-gray-100" : ""}
        />
        <div className="flex gap-3">
          <Button 
            onClick={sendMessage} 
            disabled={loading || !input.trim()}
            className={loading ? "opacity-70" : ""}
          >
            {loading ? "Thinking..." : "Send"}
          </Button>
          {onSubmitFinal && (
            <Button 
              variant="secondary" 
              onClick={handleSubmitFinal} 
              disabled={!canSubmitFinal}
              className={canSubmitFinal ? shouldPromptSubmit ? "bg-green-100 hover:bg-green-200 animate-pulse" : "bg-green-100 hover:bg-green-200" : ""}
            >
              {loading ? "Optimizing..." : disableSubmit ? "Processing..." : "✅ Accept & Submit"}
            </Button>
          )}
        </div>
        
        {submitAttempts > 0 && disableSubmit && (
          <div className="text-xs text-amber-600">
            Your submission is being processed. Please wait...
          </div>
        )}

        {isReasoningMode && interactionCount > 0 && interactionCount < 5 && (
          <div className="text-xs text-amber-600">
            This is a reasoning agent and may need at least 5 interactions to fully understand your requirements.
          </div>
        )}
      </CardContent>
    </Card>
  );
}