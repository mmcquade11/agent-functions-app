import React, { useState, useEffect, useRef } from 'react';
import Editor from "@monaco-editor/react";
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Spinner } from '@/components/ui/spinner';
import { Toaster } from "@/components/ui/toaster"
import { useToast } from "@/hooks/use-toast"

interface CodeExecutionComponentProps {
  initialCode: string;
  onCodeChange?: (code: string) => void;
}

export function CodeExecutionComponent({ initialCode, onCodeChange }: CodeExecutionComponentProps) {
  const [code, setCode] = useState<string>(initialCode || '# Enter your Python code here');
  const [output, setOutput] = useState<string>('');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [pyodide, setPyodide] = useState<any>(null);
  
  const outputRef = useRef<HTMLDivElement>(null);

  // Initialize Pyodide
  useEffect(() => {
    const loadPyodide = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Load Pyodide script dynamically
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/pyodide/v0.23.4/full/pyodide.js';
        script.async = true;
        document.body.appendChild(script);
        
        script.onload = async () => {
          try {
            // @ts-ignore - Pyodide is loaded globally
            const pyodideInstance = await window.loadPyodide({
              indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.23.4/full/',
            });
            
            // Pre-install common libraries
            await pyodideInstance.loadPackagesFromImports(`
              import numpy 
              import pandas
              import matplotlib.pyplot as plt
            `);
            
            setPyodide(pyodideInstance);
            setIsLoading(false);
            console.log("Pyodide loaded successfully");
            
            // Redirect console output
            pyodideInstance.globals.set('print_output', '');
            
            // Install a custom print function
            await pyodideInstance.runPythonAsync(`
              import sys
              from pyodide.ffi import to_js
              
              class PyodideOutput:
                  def __init__(self):
                      self.output = ""
                  
                  def write(self, text):
                      self.output += str(text)
                      return len(text)
                  
                  def flush(self):
                      pass
              
              py_output = PyodideOutput()
              sys.stdout = py_output
              sys.stderr = py_output
              
              def get_output():
                  return to_js(py_output.output)
              
              def reset_output():
                  py_output.output = ""
            `);
            
          } catch (initError) {
            console.error("Error initializing Pyodide:", initError);
            setError(`Failed to initialize Python environment: ${initError.message}`);
            setIsLoading(false);
          }
        };
        
        script.onerror = () => {
          setError("Failed to load Pyodide script. Check your internet connection.");
          setIsLoading(false);
        };
        
        return () => {
          document.body.removeChild(script);
        };
      } catch (err) {
        console.error("Error in Pyodide setup:", err);
        setError(`Error setting up Python environment: ${err.message}`);
        setIsLoading(false);
      }
    };
    
    loadPyodide();
  }, []);

  const handleCodeChange = (value: string | undefined) => {
    if (value !== undefined) {
      setCode(value);
      if (onCodeChange) {
        onCodeChange(value);
      }
    }
  };

  const executeCode = async () => {
    if (!pyodide || isExecuting) return;
    
    setIsExecuting(true);
    setOutput('');
    setError(null);
    
    try {
      // Reset output
      await pyodide.runPythonAsync("reset_output()");
      
      // Execute the code
      await pyodide.runPythonAsync(code);
      
      // Get the output
      const result = await pyodide.runPythonAsync("get_output()");
      setOutput(result);
      
      // Scroll to bottom of output
      if (outputRef.current) {
        outputRef.current.scrollTop = outputRef.current.scrollHeight;
      }
      
      toast({
        title: "Code executed successfully",
        variant: "default",
      });
    } catch (err) {
      console.error("Python execution error:", err);
      setError(`${err.message}`);
      
      // Also capture error output from stderr
      try {
        const errorOutput = await pyodide.runPythonAsync("get_output()");
        if (errorOutput) {
          setOutput(errorOutput);
        }
      } catch (_) {
        // Ignore errors when trying to get error output
      }
      
      toast({
        title: "Execution error",
        description: "There was an error executing your code.",
        variant: "destructive",
      });
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex justify-between items-center">
          <span>Python Code Execution</span>
          <Button 
            onClick={executeCode} 
            disabled={isLoading || isExecuting || !code.trim()}
          >
            {isExecuting ? (
              <>
                <Spinner size="sm" className="mr-2" /> 
                Running...
              </>
            ) : (
              "▶️ Run"
            )}
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-8">
            <Spinner size="lg" />
            <p className="mt-4 text-muted-foreground">Loading Python environment...</p>
          </div>
        ) : (
          <Tabs defaultValue="code" className="w-full">
            <TabsList>
              <TabsTrigger value="code">Code</TabsTrigger>
              <TabsTrigger value="output">Output</TabsTrigger>
            </TabsList>
            
            <TabsContent value="code" className="min-h-[400px] border rounded-md">
              <Editor
                height="400px"
                language="python"
                value={code}
                onChange={handleCodeChange}
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  lineNumbers: 'on',
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                }}
              />
            </TabsContent>
            
            <TabsContent value="output" className="min-h-[400px] border rounded-md">
              <div 
                ref={outputRef}
                className="p-4 h-[400px] font-mono text-sm overflow-y-auto bg-black text-green-400"
              >
                {error ? (
                  <div className="text-red-500">
                    {error}
                  </div>
                ) : (
                  output ? (
                    <pre className="whitespace-pre-wrap">{output}</pre>
                  ) : (
                    <div className="text-gray-500 italic">
                      {isExecuting ? "Running..." : "Run your code to see output here."}
                    </div>
                  )
                )}
              </div>
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}