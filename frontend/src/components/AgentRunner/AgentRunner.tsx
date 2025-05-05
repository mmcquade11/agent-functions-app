import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useAgentWebSocket } from "@/hooks/useAgentWebSocket";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import ReactMarkdown from 'react-markdown';
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuList,
  NavigationMenuLink,
} from "@/components/ui/navigation-menu";
import Editor from "@monaco-editor/react";
import ChatInterface from "@/components/ChatInterface";
import { CodeExecutionComponent } from "@/components/CodeExecutionComponent";
import { Spinner } from "@/components/ui/spinner";
import { Toaster } from "@/components/ui/toaster"
import { useToast } from "@/hooks/use-toast"

// Function to generate dynamic follow-up questions based on user input
const generateFollowUpQuestions = (userPrompt: string) => {
  // Extract potential services/integrations mentioned in the prompt
  const servicesMap: {[key: string]: string[]} = {
    "google drive": ["google drive", "drive", "doc", "document", "gdrive", "google doc"],
    "email": ["email", "mail", "gmail", "outlook", "send mail", "e-mail"],
    "slack": ["slack", "message", "channel", "chat", "slack channel"],
    "salesforce": ["salesforce", "crm", "customer", "lead", "opportunity"],
    "google calendar": ["calendar", "event", "schedule", "appointment", "meeting"],
    "github": ["github", "git", "repo", "code", "pull request", "repository"],
    "jira": ["jira", "ticket", "issue", "task", "atlassian"],
    "zendesk": ["zendesk", "ticket", "support", "customer service", "help desk"],
    "teams": ["teams", "microsoft teams", "channel", "teams message"],
    "database": ["database", "sql", "db", "query", "postgres", "mysql", "mongodb"]
  };
  
  // Detect which services are mentioned
  const detectedServices: string[] = [];
  const lowerPrompt = userPrompt.toLowerCase();
  
  Object.entries(servicesMap).forEach(([service, keywords]) => {
    if (keywords.some(keyword => lowerPrompt.includes(keyword))) {
      detectedServices.push(service);
    }
  });
  
  // If no specific services detected, use general questions
  if (detectedServices.length === 0) {
    return `I understand you want to create an agent that will ${userPrompt}. To implement this effectively, I'll need some additional details:

1. Which specific systems or data sources will this agent need to access?
2. What specific actions should the agent take with the data?
3. Where should the results be sent or stored?`;
  }
  
  // Generate service-specific questions
  let questions = `I understand you want to create an agent that will ${userPrompt}. To implement this effectively, I'll need some specific details:\n\n`;
  
  detectedServices.forEach(service => {
    if (service === "google drive") {
      questions += "- For Google Drive access: How should files be identified (by ID, name, or search)? What permissions will be needed?\n";
    }
    else if (service === "email") {
      questions += "- For email functionality: Who should receive the emails? Are there specific formatting requirements?\n";
    }
    else if (service === "slack") {
      questions += "- For Slack integration: Which channels or users should receive messages? Any specific formatting requirements?\n";
    }
    else if (service === "salesforce") {
      questions += "- For Salesforce integration: Which objects will be accessed or modified? What specific operations are needed?\n";
    }
    else if (service === "github") {
      questions += "- For GitHub integration: Which repositories will be accessed? What specific operations are needed?\n";
    }
    else {
      questions += `- For ${service} integration: What specific operations are needed? What authentication method will be used?\n`;
    }
  });
  
  questions += "\nAny additional requirements for how the agent should process or transform the data?";
  
  return questions;
};

// Function to extract Python code from raw text
const extractPythonCode = (text: string): string => {
  // First, try to extract code blocks with triple backticks
  const codeBlockRegex = /```(?:python)?\s*([\s\S]*?)```/g;
  const codeBlocks = [...text.matchAll(codeBlockRegex)].map(match => match[1].trim());
  
  if (codeBlocks.length > 0) {
    return codeBlocks.join('\n\n');
  }
  
  // Look for Python patterns (imports, functions, classes)
  const pythonPatterns = [
    { pattern: /import\s+[\w.]+/, type: 'import' },
    { pattern: /from\s+[\w.]+\s+import/, type: 'import' },
    { pattern: /def\s+[\w_]+\s*\([\s\S]*?\):/, type: 'function' },
    { pattern: /class\s+[\w_]+[\s\S]*?:/, type: 'class' }
  ];
  
  // Find the earliest occurrence of any Python pattern
  let earliestIndex = -1;
  
  for (const { pattern } of pythonPatterns) {
    const match = text.match(pattern);
    if (match && match.index !== undefined) {
      if (earliestIndex === -1 || match.index < earliestIndex) {
        earliestIndex = match.index;
      }
    }
  }
  
  if (earliestIndex !== -1) {
    return text.substring(earliestIndex);
  }
  
  // Check for narrative markers
  const codeMarkers = [
    "Here's the code:",
    "Here is the code:",
    "The code is:",
    "I'll write the code:",
    "Here's the Python code:",
    "The Python implementation:",
    "Here's my implementation:"
  ];
  
  for (const marker of codeMarkers) {
    const markerIndex = text.indexOf(marker);
    if (markerIndex !== -1) {
      const startIndex = markerIndex + marker.length;
      const nextTripleBacktick = text.indexOf("```", startIndex);
      
      // If there's a code block after the marker, skip to the next strategy
      if (nextTripleBacktick !== -1 && nextTripleBacktick - startIndex < 50) {
        continue;
      }
      
      return text.substring(startIndex).trim();
    }
  }
  
  // If nothing works, return placeholder
  return "# Could not automatically extract code\n# Please check the Raw Response tab and copy the code manually";
};

export function AgentRunner() {
  const { getAccessTokenSilently } = useAuth0();

  const [userPrompt, setUserPrompt] = useState("");
  const [chatMode, setChatMode] = useState<"initial" | "reasoning" | "optimize">("initial");
  const [chatSeed, setChatSeed] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null);
  const [finalCode, setFinalCode] = useState<string>("");
  const [runLogs, setRunLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [reasoningMode, setReasoningMode] = useState<boolean | null>(null);
  const [claudeResponse, setClaudeResponse] = useState<string>("");
  const [agentLog, setAgentLog] = useState<string>("");
  const [apiRetries, setApiRetries] = useState<number>(0);
  const [apiErrors, setApiErrors] = useState<string[]>([]);
  const [showCodeExecution, setShowCodeExecution] = useState<boolean>(false);
  
  // New states for the clarification stage
  const [claudeStage, setClaudeStage] = useState<"waiting" | "clarification" | "codeGeneration">("waiting");
  const [missingParameters, setMissingParameters] = useState<any[]>([]);
  const [userParams, setUserParams] = useState<{[key: string]: string}>({});
  const [showParameterForm, setShowParameterForm] = useState<boolean>(false);
  const [clarifiedPrompt, setClarifiedPrompt] = useState<string | null>(null);
  
  // State for manual mode selection
  const [routingMode, setRoutingMode] = useState<"auto" | "manual">("auto");
  const [manualReasoning, setManualReasoning] = useState<boolean>(false);
  
  // Process incoming Claude messages directly
  const processClaudeMessage = useCallback((message: any) => {
    if (message.phase === "claude" && message.type === "text" && message.content) {
      console.log("Adding content to Claude response:", message.content.substring(0, 30) + "...");
      setClaudeResponse(prev => prev + message.content);
      
      // Try to identify if Claude is asking for parameters instead of generating code
      if (claudeStage === "waiting" && !showParameterForm) {
        // Check if the response looks like Claude is asking for information
        // This runs once after we've accumulated some response
        if (message.content.length > 100 && !finalCode) {
          const isAskingQuestions = /(?:need|additional) information|(?:before|can) (?:I|we) (?:can|could)|(?:What|Do you|Would you|Could you)\?/.test(message.content);
          
          if (isAskingQuestions) {
            // Pause the WebSocket connection
            console.log("Detected Claude asking for parameters, pausing response streaming");
            
            // Extract parameters from Claude's questions
            const questionRegex = /(?:What|How|Do you|Could you|Would you)[^.?!]*\?/g;
            const questions = message.content.match(questionRegex) || [];
            
            // Convert questions to parameters
            const extractedParams: any[] = questions.map((question: string, index: number) => {
              // Try to identify parameter type from question
              let paramName = "param_" + (index + 1);
              let required = true;
              
              if (question.toLowerCase().includes("google drive") || question.toLowerCase().includes("file id")) {
                paramName = "document_id";
              } else if (question.toLowerCase().includes("oauth") || question.toLowerCase().includes("credentials")) {
                paramName = "auth_method";
                required = false;
              } else if (question.toLowerCase().includes("email")) {
                paramName = "email_recipient";
              } else if (question.toLowerCase().includes("summariz") || question.toLowerCase().includes("length")) {
                paramName = "summary_level";
                required = false;
              }
              
              return {
                name: paramName,
                description: question,
                default: null,
                required: required
              };
            });
            
            if (extractedParams.length > 0) {
              setMissingParameters(extractedParams);
              setShowParameterForm(true);
              setClaudeStage("clarification");
            }
          }
        }
      }
    } else if (message.phase === "reasoning" && message.content) {
      // Handle reasoning-specific messages
      console.log(`Reasoning ${message.type}:`, message.content);
      setAgentLog(prev => prev + `\n\n--- ${message.type} ---\n${message.content}`);
    }
  }, [claudeStage, finalCode, showParameterForm]);
  
  // Claude integration via WebSocket with our message processor
  const { messages, isStreaming, pauseStream, resumeStream } = useAgentWebSocket(
    submittedPrompt, 
    processClaudeMessage
  );

  // Clear API error state when changing modes
  useEffect(() => {
    setApiErrors([]);
    setApiRetries(0);
  }, [chatMode, routingMode]);

  // Extract code from Claude response
  useEffect(() => {
    if (!claudeResponse || isStreaming) return;
    
    // If streaming is done, try to extract code
    const extractedCode = extractPythonCode(claudeResponse);
    setFinalCode(extractedCode);
    
    // If we have code, show the code execution component
    if (extractedCode && extractedCode !== "# Could not automatically extract code\n# Please check the Raw Response tab and copy the code manually") {
      setShowCodeExecution(true);
    }
  }, [claudeResponse, isStreaming]);

  // Handle API errors with retries and fallbacks
  const handleApiError = (endpoint: string, error: any) => {
    console.error(`Error in ${endpoint}:`, error);
    
    // Increment retry count
    const newRetryCount = apiRetries + 1;
    setApiRetries(newRetryCount);
    
    // Add to errors log
    setApiErrors(prev => [...prev, `[${new Date().toISOString()}] ${endpoint} error: ${error.message || 'Unknown error'}`]);
    
    // Toast notification for user
    toast({
      title: "Connection issue",
      description: "Experienced a temporary issue. Trying again with simplified approach.",
      variant: "destructive",
    });
    
    // Return fallback based on context and retry count
    if (endpoint.includes("optimize-prompt")) {
      if (newRetryCount > 2) {
        // After multiple retries, give simplified fallback
        return "I have all the information I need. Let's proceed with creating your agent. Would you like me to show you the implementation now?";
      } else {
        return "Thanks for those details. Do you have any specific authentication requirements or preferences for how the results should be formatted?";
      }
    } else if (endpoint.includes("route-prompt")) {
      // Default to non-reasoning mode on routing errors
      return false;
    } else {
      return "I've processed your request and I'm ready to implement your agent. Would you like to proceed?";
    }
  };

  // Step 1: Initial prompt routing with support for manual and auto mode
  const routePrompt = async () => {
    if (!userPrompt.trim()) return;
    
    setIsLoading(true);
    setStatus(null);
    try {
      const token = await getAccessTokenSilently();
      console.log("Starting prompt routing for:", userPrompt);
      
      // Determine if reasoning is needed based on mode
      let needsReasoning = false;
      
      if (routingMode === "auto") {
        try {
          // Call the route-prompt endpoint to determine if reasoning is needed
          const res = await fetch("http://localhost:8000/api/v1/prompt/route-prompt", {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ prompt: userPrompt }),
            // Add timeout for fetch
            signal: AbortSignal.timeout(10000),
          });

          if (!res.ok) {
            const errText = await res.text();
            console.error(`API error (${res.status}): ${errText}`);
            throw new Error(`API error: ${res.status} - ${errText}`);
          }

          const data = await res.json();
          needsReasoning = data.needs_reasoning;
          console.log("Auto-detected reasoning needed:", needsReasoning);
        } catch (err) {
          console.error("Error in route-prompt:", err);
          // Use fallback on error
          needsReasoning = handleApiError("route-prompt", err);
        }
      } else {
        // Use the manually selected mode
        needsReasoning = manualReasoning;
        console.log("Manually selected reasoning:", needsReasoning);
      }
      
      // Store reasoning mode for UI display
      setReasoningMode(needsReasoning);

      // Set up initial chat with a dynamic, service-specific message
      const dynamicMessage = needsReasoning
        ? `I'll help you think through this task step by step. Let's break down what you want to accomplish with "${userPrompt}". ${generateFollowUpQuestions(userPrompt)}`
        : generateFollowUpQuestions(userPrompt);
      
      setChatSeed([
        { role: "user", content: userPrompt },
        { role: "assistant", content: dynamicMessage },
      ]);

      // Set chat mode based on reasoning need
      setChatMode(needsReasoning ? "reasoning" : "optimize");
      
      // Store the original prompt and reasoning flag
      sessionStorage.setItem('originalPrompt', userPrompt);
      sessionStorage.setItem('needsReasoning', needsReasoning.toString());
      
    } catch (err) {
      console.error("Error routing prompt:", err);
      setStatus("Error routing prompt. Please try again or use manual mode.");
      // Show toast notification to user
      toast({
        title: "Error",
        description: "Couldn't process your request. Please try again or switch to manual mode.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Step 2: Handle chat message sending (either reasoning or optimization mode)
  const handleChatSend = async (message: string) => {
    console.log(`Handling chat message in ${chatMode} mode:`, message);
    try {
      const token = await getAccessTokenSilently();
      
      // Use the appropriate endpoint based on chat mode
      const endpoint = chatMode === "reasoning" 
        ? "agents/reasoning-agent" 
        : "prompt/optimize-prompt";
      
      console.log(`Sending to endpoint: ${endpoint}`);
      
      // Enhanced fetch with timeout
      const res = await fetch(`http://localhost:8000/api/v1/${endpoint}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: message }),
        signal: AbortSignal.timeout(15000),
      });

      if (!res.ok) {
        console.error(`API error: ${res.status}`);
        const errorText = await res.text();
        throw new Error(`API error (${res.status}): ${errorText}`);
      }

      const data = await res.json();
      console.log(`Response from ${endpoint}:`, data);
      
      // Return the appropriate response field
      if (chatMode === "reasoning") {
        return data.reasoned_prompt || "I now have enough information to proceed. What else would you like to add before we implement this agent?";
      } else {
        return data.optimized_prompt || "Thank you for the details. Based on what you've shared, I understand what you need. Ready to create this agent?";
      }
    } catch (err) {
      console.error(`Error in ${chatMode} chat:`, err);
      // Use fallback responses
      return handleApiError(`${chatMode} chat`, err);
    }
  };

  // Step 3: Final submit from chat interface - optimize and send to Claude
  const handleFinalSubmit = async (finalPrompt: string) => {
    console.log("Final submit with prompt:", finalPrompt);
    setIsLoading(true);
    
    // Reset states for new submission
    setClaudeResponse("");
    setFinalCode("");
    setAgentLog("");
    setStatus(null);
    setShowParameterForm(false);
    setMissingParameters([]);
    setUserParams({});
    setClaudeStage("waiting");
    setShowCodeExecution(false);
    
    try {
      const token = await getAccessTokenSilently();
      
      // Call optimize-prompt endpoint to get the structured version for Claude
      let optimizedPrompt = "";
      
      try {
        const optimizeRes = await fetch("http://localhost:8000/api/v1/prompt/optimize-prompt", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ prompt: finalPrompt }),
          signal: AbortSignal.timeout(20000),
        });

        if (!optimizeRes.ok) {
          const errText = await optimizeRes.text();
          console.error(`Optimize API error (${optimizeRes.status}): ${errText}`);
          throw new Error(`Optimize API error: ${optimizeRes.status}`);
        }

        const optimizeData = await optimizeRes.json();
        optimizedPrompt = optimizeData.optimized_prompt;
      } catch (err) {
        console.error("Error in final optimization:", err);
        
        // Create fallback prompt based on detected services
        const lowerPrompt = finalPrompt.toLowerCase();
        const hasDrive = lowerPrompt.includes("google drive") || lowerPrompt.includes("drive");
        const hasEmail = lowerPrompt.includes("email") || lowerPrompt.includes("mail");
        
        // Structured fallback based on detected services
        optimizedPrompt = `
1. TASK OVERVIEW
Create an agent that ${hasDrive ? "retrieves documents from Google Drive" : "processes data"} ${hasEmail ? "and sends results via email" : "and returns results"}.

2. REQUIRED CAPABILITIES
${hasDrive ? "- Google Drive API access\n" : ""}${hasEmail ? "- Email sending capability\n" : ""}

3. IMPLEMENTATION REQUIREMENTS
- Implement secure authentication
- Include proper error handling
- Use efficient code patterns

4. OUTPUT REQUIREMENTS
- Provide clear success/failure messages
- Format results clearly

5. TOOL-USE FORMAT
Implement this using Claude's tool-use capabilities to create a functional agent.`;
        
        // Show toast to inform user
        toast({
          title: "Using simplified format",
          description: "Using an alternative approach due to temporary connection issues.",
          variant: "default",
        });
      }
      
      // Enhance the optimized prompt to better instruct Claude
      const enhancedPrompt = `
${optimizedPrompt}

IMPORTANT IMPLEMENTATION INSTRUCTIONS:
1. Generate complete, working code implementing this solution
2. Use default values for any missing information rather than asking questions
3. For Google Drive access, use a service account approach with credentials file
4. For document IDs, use placeholder IDs that the user can replace
5. For email credentials, use placeholder SMTP settings the user can replace
6. Always include detailed comments explaining what needs to be configured
7. Provide complete, runnable code - do not wait for more information

Example defaults to use:
- Google Drive document ID: Use "DOCUMENT_ID_HERE" as placeholder
- Authentication: Default to a service account approach with "service_account.json"
- Email: Use SMTP with placeholder credentials for Gmail
- Summarization: Default to extractive summarization at 20% length
`;
      
      console.log("Using enhanced prompt:", enhancedPrompt);
      
      // Store the optimized prompt for Claude
      sessionStorage.setItem('optimizedPrompt', enhancedPrompt);
      
      // Set the optimized prompt to be sent to Claude via WebSocket
      setSubmittedPrompt(enhancedPrompt);
      
      // Reset the chat mode to show Claude's output
      setChatMode("initial");
      
    } catch (err) {
      console.error("Error in final submit:", err);
      setStatus("Error preparing prompt. Using a simplified approach.");
      
      // Create a minimal fallback and continue
      const fallbackPrompt = `Create a Python agent that processes data and produces results based on the following requirements: ${finalPrompt.substring(0, 200)}...`;
      
      sessionStorage.setItem('optimizedPrompt', fallbackPrompt);
      setSubmittedPrompt(fallbackPrompt);
      setChatMode("initial");
      
      toast({
        title: "Connection issue",
        description: "Using simplified approach due to connection problems.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Process user parameter form submission
  const handleParameterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required parameters
    const missingRequired = missingParameters.filter(
      param => param.required && (!userParams[param.name] || !userParams[param.name].trim())
    );
    
    if (missingRequired.length > 0) {
      toast({
        title: "Missing required parameters",
        description: `Please provide values for: ${missingRequired.map(p => p.name).join(', ')}`,
        variant: "destructive",
      });
      return;
    }
    
    setIsLoading(true);
    
    try {
      // Get the original prompt from session storage
      const originalPrompt = sessionStorage.getItem('optimizedPrompt') || "";
      
      // Create a new prompt with the parameters
      const parameterizedPrompt = `
${originalPrompt}

The user has provided the following parameter values:
${Object.entries(userParams).map(([key, value]) => `- ${key}: ${value}`).join('\n')}

INSTRUCTION: Generate complete, working code implementing this solution using the provided parameters.
Use tool-calling format to create a comprehensive implementation. Include proper error handling,
clear documentation, and ensure the code is ready to run. DO NOT ask for any additional information.
`;
      
      // Update the session storage
      sessionStorage.setItem('optimizedPrompt', parameterizedPrompt);
      
      // Set the clarified prompt
      setClarifiedPrompt(parameterizedPrompt);
      
      // Continue with Claude code generation
      setClaudeStage("codeGeneration");
      setShowParameterForm(false);
      
      // Resume the WebSocket with the new prompt
      setSubmittedPrompt(parameterizedPrompt);
      
    } catch (err) {
      console.error("Error in parameter submission:", err);
      setStatus("Error applying parameters. Using defaults instead.");
      
      // Fall back to the original prompt
      setClaudeStage("codeGeneration");
      setShowParameterForm(false);
      resumeStream();
      
      toast({
        title: "Parameter error",
        description: "Could not apply your parameters. Using default values instead.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Step 4: Agent actions (execute, test, schedule) using the V2 API
  const sendAgentAction = async (action: "execute" | "test" | "schedule") => {
    setIsLoading(true);
    setStatus(null);
    try {
      const token = await getAccessTokenSilently();
      
      // Get the prompts and reasoning flag from session storage
      const originalPrompt = sessionStorage.getItem('originalPrompt') || "";
      const optimizedPrompt = sessionStorage.getItem('optimizedPrompt') || "";
      const needsReasoning = sessionStorage.getItem('needsReasoning') === "true";
      
      console.log(`Sending ${action} request with reasoning=${needsReasoning}`);
      
      // Add error handling with timeout
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      
      try {
        // Use the new V2 API endpoints
        const res = await fetch(`http://localhost:8000/api/v1/agents/v2/${action}`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            prompt: originalPrompt,
            optimizedPrompt: optimizedPrompt,
            needsReasoning: needsReasoning,
            code: finalCode
          }),
          signal: controller.signal,
        });
        
        clearTimeout(timeout);

        if (!res.ok) {
          const errText = await res.text();
          setStatus(`[error] ${errText}`);
          throw new Error(`API error (${res.status}): ${errText}`);
        }

        if (action === "execute") {
          const reader = res.body?.getReader();
          const decoder = new TextDecoder();
          setRunLogs([]);

          if (reader) {
            try {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                setRunLogs((prev) => [...prev, chunk]);
              }
              setStatus("Execution complete");
            } catch (e) {
              console.error("Error reading stream:", e);
              setStatus(`[error] Error reading response stream: ${e.message || 'Unknown error'}`);
            }
          }
        } else {
          const data = await res.json();
          setStatus(data.message || `${action} completed successfully`);
        }
      } catch (err) {
        console.error(`Error in ${action} action:`, err);
        
        if (err.name === 'AbortError') {
          setStatus(`[error] Request timeout. The operation took too long to complete.`);
          toast({
            title: "Request timeout",
            description: "The operation took too long. Please try again.",
            variant: "destructive",
          });
        } else {
          setStatus(`[error] ${err.message || `Error during ${action}`}`);
          toast({
            title: "Error",
            description: `Failed to ${action} the agent. Please try again.`,
            variant: "destructive",
          });
        }
      }
    } catch (err) {
      console.error(`General error in ${action}:`, err);
      setStatus(`[error] ${err.message || `Something went wrong during ${action}`}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <NavigationMenu className="px-6 py-4 border-b">
        <NavigationMenuList className="flex space-x-6">
          <NavigationMenuItem><NavigationMenuLink href="/dashboard">Dashboard</NavigationMenuLink></NavigationMenuItem>
          <NavigationMenuItem><NavigationMenuLink href="/agents/create">Create Agent</NavigationMenuLink></NavigationMenuItem>
          <NavigationMenuItem><NavigationMenuLink href="/agents">Agent Library</NavigationMenuLink></NavigationMenuItem>
          <NavigationMenuItem><NavigationMenuLink href="/login">Logout</NavigationMenuLink></NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenu>

      <div className="max-w-4xl mx-auto space-y-6 py-6">
        {chatMode === "initial" && !submittedPrompt && (
          <Card>
            <CardContent className="space-y-4 p-4">
              {/* Agent mode selection */}
              <div className="mb-6 space-y-4 border-b pb-4">
                <h3 className="text-lg font-medium">Agent Type</h3>
                
                <RadioGroup 
                  defaultValue="auto" 
                  value={routingMode}
                  onValueChange={(val) => setRoutingMode(val as "auto" | "manual")}
                  className="flex items-center space-x-6"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="auto" id="auto" />
                    <Label htmlFor="auto">Auto-detect</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="manual" id="manual" />
                    <Label htmlFor="manual">Manual selection</Label>
                  </div>
                </RadioGroup>
                
                {routingMode === "manual" && (
                  <div className="flex items-center space-x-4 mt-2 ml-4">
                    <Switch 
                      id="reasoning-mode"
                      checked={manualReasoning}
                      onCheckedChange={setManualReasoning}
                    />
                    <Label htmlFor="reasoning-mode">
                      {manualReasoning ? "🧠 Use reasoning agent (for complex tasks)" : "🤖 Use task-focused agent (for simpler tasks)"}
                    </Label>
                  </div>
                )}
              </div>
              
              <Textarea
                placeholder="What do you want your agent to do?"
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                rows={4}
              />
              <Button onClick={routePrompt} disabled={isLoading || !userPrompt.trim()}>
                {isLoading ? "Processing..." : "→ Next"}
              </Button>
            </CardContent>
          </Card>
        )}

        {apiErrors.length > 0 && (
          <Card className="bg-amber-50">
            <CardContent className="p-4">
              <details>
                <summary className="text-xs text-amber-800 cursor-pointer">Diagnostic Information (click to expand)</summary>
                <div className="mt-2 text-xs font-mono text-amber-800 p-2 bg-amber-100 rounded max-h-32 overflow-y-auto">
                  {apiErrors.map((err, i) => (
                    <div key={i}>{err}</div>
                  ))}
                </div>
                <div className="mt-2 text-xs text-amber-800">
                  Using fallback responses. Retry or refresh page if issues persist.
                </div>
              </details>
            </CardContent>
          </Card>
        )}

        {reasoningMode !== null && (chatMode === "reasoning" || chatMode === "optimize") && (
          <>
            <Alert className={reasoningMode ? "bg-amber-50" : "bg-blue-50"}>
              <AlertTitle>
                {reasoningMode 
                  ? "🧠 Reasoning Agent Activated" 
                  : "🤖 Task-Focused Agent Activated"}
              </AlertTitle>
              <AlertDescription>
                {reasoningMode
                  ? "This task requires step-by-step reasoning. I'll help you break it down thoroughly."
                  : "This task seems straightforward. I'll help you refine it for the best results."}
              </AlertDescription>
            </Alert>
            
            <ChatInterface
              initialMessages={chatSeed}
              onSend={handleChatSend}
              onSubmitFinal={handleFinalSubmit}
              disableSubmit={isLoading}
              isReasoningMode={reasoningMode}
            />
          </>
        )}

        {/* Parameter Collection Form */}
        {showParameterForm && (
          <Card className="mb-6 border-2 border-amber-300">
            <CardHeader>
              <CardTitle>Additional Information Needed</CardTitle>
              <div className="text-sm text-muted-foreground">
                Please provide the following details to complete your agent:
              </div>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleParameterSubmit} className="space-y-4">
                {missingParameters.map((param) => (
                  <div key={param.name} className="space-y-2">
                    <Label htmlFor={param.name}>
                      {param.name.replace(/_/g, ' ')} {param.required && <span className="text-red-500">*</span>}
                    </Label>
                    <Input 
                      id={param.name}
                      placeholder={param.description}
                      value={userParams[param.name] || ''}
                      onChange={(e) => setUserParams({
                        ...userParams,
                        [param.name]: e.target.value
                      })}
                      required={param.required}
                    />
                    <p className="text-sm text-muted-foreground">{param.description}</p>
                  </div>
                ))}
                <Button type="submit" disabled={isLoading}>
                  {isLoading ? "Processing..." : "Generate Agent"}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Loading States */}
        {claudeStage === "clarification" && !showParameterForm && (
          <div className="text-center py-4">
            <Spinner />
            <p className="text-sm text-muted-foreground mt-2">Analyzing requirements...</p>
          </div>
        )}

        {claudeStage === "codeGeneration" && (
          <div className="text-center py-4">
            <Spinner />
            <p className="text-sm text-muted-foreground mt-2">Generating agent code...</p>
          </div>
        )}

        {submittedPrompt && !showParameterForm && (
          <Card>
            <CardContent className="p-4 space-y-4">
              <div className="text-xs text-muted-foreground font-mono">
                {isStreaming ? "Agent is generating response..." : "Agent Output"}
              </div>
              
              <Tabs defaultValue="code" className="w-full">
                <TabsList>
                  <TabsTrigger value="code">Code</TabsTrigger>
                  <TabsTrigger value="explanation">Explanation</TabsTrigger>
                  {reasoningMode && <TabsTrigger value="reasoning">Reasoning</TabsTrigger>}
                  <TabsTrigger value="raw">Raw Response</TabsTrigger>
                </TabsList>
                
                <TabsContent value="code" className="min-h-[400px] border rounded-md p-2">
                  <Editor
                    height="400px"
                    language="python"
                    value={finalCode || "# Waiting for code generation..."}
                    onChange={(val) => setFinalCode(val || "")}
                    options={{ minimap: { enabled: false }, fontSize: 14 }}
                  />
                </TabsContent>
                
                <TabsContent value="explanation" className="min-h-[400px] border rounded-md p-4 overflow-y-auto">
                  <div className="prose max-w-none">
                    <ReactMarkdown>
                      {claudeResponse.replace(/```[\s\S]*?```/g, '')}
                    </ReactMarkdown>
                  </div>
                </TabsContent>
                
                {reasoningMode && (
                  <TabsContent value="reasoning" className="min-h-[400px] border rounded-md p-4 overflow-y-auto">
                    <div className="prose max-w-none">
                      <ReactMarkdown>
                        {agentLog}
                      </ReactMarkdown>
                    </div>
                  </TabsContent>
                )}
                
                <TabsContent value="raw" className="min-h-[400px] border rounded-md p-4 overflow-y-auto">
                  <pre className="whitespace-pre-wrap text-sm">{claudeResponse}</pre>
                </TabsContent>
              </Tabs>
              
              <div className="flex gap-3 pt-2">
                <Button 
                  onClick={() => sendAgentAction("execute")} 
                  disabled={isLoading || !finalCode || finalCode === "# Waiting for code generation..."}
                >
                  {isLoading ? "Processing..." : "🚀 Run on Server"}
                </Button>
                <Button 
                  onClick={() => sendAgentAction("test")} 
                  disabled={isLoading || !finalCode || finalCode === "# Waiting for code generation..."}
                >
                  {isLoading ? "Processing..." : "🧪 Test"}
                </Button>
                <Button 
                  onClick={() => sendAgentAction("schedule")} 
                  disabled={isLoading || !finalCode || finalCode === "# Waiting for code generation..."}
                >
                  {isLoading ? "Processing..." : "📅 Schedule"}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => setShowCodeExecution(prev => !prev)}
                  disabled={!finalCode || finalCode === "# Waiting for code generation..."}
                >
                  {showCodeExecution ? "Hide Execution" : "🖥️ Run in Browser"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Code Execution Component */}
        {showCodeExecution && finalCode && finalCode !== "# Waiting for code generation..." && (
          <CodeExecutionComponent 
            initialCode={finalCode} 
            onCodeChange={(newCode) => setFinalCode(newCode)}
          />
        )}

        {runLogs.length > 0 && (
          <Card>
            <CardContent className="p-4 space-y-2">
              <div className="text-xs text-muted-foreground font-mono">Execution Output</div>
              <div className="max-h-[300px] overflow-y-auto border rounded p-2 bg-gray-50">
                {runLogs.map((line, idx) => (
                  <pre key={idx} className="text-sm whitespace-pre-wrap">{line}</pre>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {status && (
          <Card>
            <CardContent className="p-4">
              <div className={`text-sm font-mono ${status.includes("error") ? "text-red-600" : "text-green-600"}`}>
                {status}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}