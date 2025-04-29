# app/services/orchestrator.py

import asyncio
import traceback
import contextlib
import uuid
from typing import Optional, Dict
from openai import AsyncOpenAI
from app.core.config import settings
from app.websockets.manager import websocket_manager

class ExecutionOrchestrator:
    def __init__(self, session_id: str):
        self.websocket_manager = websocket_manager
        self.session_id = session_id

    async def run_execution(self, prompt: str, needs_reasoning: bool, user_arcee_token: Optional[str]) -> str:
        try:
            enhanced_prompt = prompt

            if needs_reasoning:
                await self._send_log("Starting reasoning...")
                reasoning_output = await self._call_reasoning(prompt, user_arcee_token)
                await self._send_log("Reasoning completed.")

                # Merge reasoning + original prompt
                enhanced_prompt = f"{prompt}\n\n# Reasoning Plan:\n{reasoning_output}"

            await self._send_log("Calling Claude to generate agent code...")
            agent_code = await self._call_claude(enhanced_prompt)
            await self._send_log("Agent code generated.")

            await self._send_log("Starting agent execution...")
            exec_output = await self._execute_code(agent_code)
            await self._send_log("Agent execution completed.")

            return exec_output

        except Exception as e:
            error_trace = traceback.format_exc()
            await self._send_log(f"Execution failed: {str(e)}\n{error_trace}")
            raise

    async def _call_reasoning(self, prompt: str, user_arcee_token: Optional[str]) -> str:
        client = AsyncOpenAI(
            base_url=settings.CONDUCTOR_BASE_URL,
            api_key=user_arcee_token or settings.ARCEE_CONDUCTOR_SYSTEM_TOKEN
        )

        response = await client.chat.completions.create(
            model="auto-reasoning",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=1.0,
        )

        reasoning_output = response.choices[0].message.content
        return reasoning_output

    async def _call_claude(self, prompt: str) -> str:
        """
        Real call to Claude 3.7 model for agent code generation.
        """

        client = AsyncOpenAI(
            base_url=settings.CLAUDE_BASE_URL,
            api_key=settings.CLAUDE_API_KEY,
        )

        response = await client.chat.completions.create(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            top_p=1.0,
        )

        generated_code = response.choices[0].message.content
        return generated_code


    async def _execute_code(self, code: str) -> str:
        namespace: Dict = {}
        stdout_capture = []

        @contextlib.contextmanager
        def capture_stdout():
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()
            try:
                yield mystdout
            finally:
                sys.stdout = old_stdout

        try:
            await self._send_log("[Agent Code] Starting execution...")
            await self._send_log(f"[Agent Code] {code}")  # ✅ Log the actual code received

            with capture_stdout() as mystdout:
                exec(code, namespace)
                if "run_agent" in namespace:
                    namespace["run_agent"]()
                else:
                    raise ValueError("No run_agent() function found in generated code.")
            stdout_content = mystdout.getvalue()
            for line in stdout_content.strip().splitlines():
                await self._send_log(f"[Agent Log] {line}")
            return stdout_content
        except Exception as e:
            error_trace = traceback.format_exc()
            await self._send_log(f"Code execution error: {str(e)}\n{error_trace}")
            raise

    async def _send_log(self, message: str):
        print(f"[Orchestrator Log] {message}")  # ✅ Also print to server console
        await self.websocket_manager.broadcast_log(
            run_id=self.session_id,
            log_data={"message": message}
        )


