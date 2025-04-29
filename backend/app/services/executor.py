from typing import Dict, List, Any, Optional, Callable, Union, Tuple, Set
import logging
import traceback
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import concurrent.futures
from collections import defaultdict
from app.websockets.manager import websocket_manager

from app.models import Workflow, WorkflowExecution, ExecutionLog
from app.db.session import SessionLocal

# Set up logger for the workflow engine
logger = logging.getLogger(__name__)

# In app/services/executor.py

async def execute_workflow(
    db,
    workflow_id: str,
    inputs: Dict[str, Any],
    executed_by: str
) -> WorkflowExecution:
    """
    Create a new workflow execution.
    
    Args:
        db: Database session
        workflow_id: ID of the workflow to execute
        inputs: Input parameters for the workflow
        executed_by: ID of the user or system initiating the execution
        
    Returns:
        The created workflow execution
    """
    # Create execution record
    execution = WorkflowExecution(
        workflow_id=workflow_id,
        status="pending",
        execution_inputs=inputs,
        executed_by=executed_by
    )
    
    db.add(execution)
    await db.flush()
    
    # Create initial log entry
    log_entry = ExecutionLog(
        execution_id=execution.id,
        level="INFO",
        message=f"Execution created and queued",
        metadata={
            "workflow_id": workflow_id,
            "inputs": inputs,
            "executed_by": executed_by
        }
    )
    
    db.add(log_entry)
    await db.commit()
    await db.refresh(execution)
    
    return execution

class WorkflowEngine:
    """
    Engine for executing workflow definitions.
    
    The WorkflowEngine executes a workflow defined as a list of nodes (functions)
    sequentially or in parallel, with support for conditional branching.
    Each node can receive input (previous node output) and return output.
    If any node throws an error, it's caught and logged without crashing the workflow.
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the workflow engine.
        
        Args:
            db_session (AsyncSession): SQLAlchemy async database session
        """
        self.db_session = db_session
        
    async def execute_workflow(
        self, 
        workflow_id: str, 
        execution_id: str,
        initial_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow by its ID.
        
        Args:
            workflow_id (str): ID of the workflow to execute
            execution_id (str): ID of the current execution
            initial_input (Dict[str, Any], optional): Initial input data for the workflow
            
        Returns:
            Dict[str, Any]: Results of the workflow execution including
                outputs from each node and overall execution status
        """
        # Get the workflow definition
        workflow = await self._get_workflow(workflow_id)
        if not workflow:
            await self._log_execution_error(
                execution_id, 
                f"Workflow with ID {workflow_id} not found", 
                step_id="workflow_lookup"
            )
            return {"success": False, "error": f"Workflow with ID {workflow_id} not found"}
        
        # Parse the workflow definition
        workflow_def = workflow.workflow_definition
        steps = workflow_def.get("steps", [])
        connections = workflow_def.get("connections", [])
        
        if not steps:
            await self._log_execution_error(
                execution_id, 
                "Workflow has no steps defined", 
                step_id="workflow_validation"
            )
            return {"success": False, "error": "Workflow has no steps defined"}
        
        # Prepare execution context
        context = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "variables": workflow_def.get("variables", {}),
            "output": initial_input or {},
            "start_time": datetime.utcnow(),
            "steps_results": {},
            "branches_taken": {}  # Track branches taken in conditional paths
        }
        
        # Build the step dependency graph
        dependency_graph = self._build_dependency_graph(steps, connections)
        
        # Execute workflow using the dependency graph
        success = await self._execute_workflow_graph(
            execution_id,
            steps,
            dependency_graph,
            initial_input or {},
            context
        )
        
        # Calculate overall execution status
        context["end_time"] = datetime.utcnow()
        context["success"] = success
        context["duration_seconds"] = (context["end_time"] - context["start_time"]).total_seconds()
        
        # Log final execution status
        if success:
            await self._log_execution_info(
                execution_id,
                f"Workflow execution completed successfully: {workflow.name}",
                step_id="workflow_complete",
                metadata={
                    "duration_seconds": context["duration_seconds"],
                    "branches_taken": context["branches_taken"]
                }
            )
        else:
            await self._log_execution_warning(
                execution_id,
                f"Workflow execution completed with errors: {workflow.name}",
                step_id="workflow_complete",
                metadata={
                    "duration_seconds": context["duration_seconds"],
                    "branches_taken": context["branches_taken"]
                }
            )
            
        # Update execution record with final status
        await self._update_execution_status(
            execution_id, 
            "completed" if success else "failed",
            context
        )
        # Broadcast run completion and close all WebSocket connections
        await websocket_manager.broadcast_run_completion(execution_id, success)

        return context
    
    def _build_dependency_graph(
        self, 
        steps: List[Dict[str, Any]], 
        connections: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build a graph representation of the workflow.
        
        Args:
            steps (List[Dict[str, Any]]): List of step definitions
            connections (List[Dict[str, Any]]): List of connections between steps
            
        Returns:
            Dict[str, Dict[str, Any]]: Dependency graph where keys are step IDs and
                values are dictionaries with 'predecessors', 'successors', and 'step' data
        """
        # Initialize the graph with all steps
        graph = {}
        for step in steps:
            step_id = step.get("id")
            if not step_id:
                continue
                
            graph[step_id] = {
                "predecessors": [],  # List of step IDs that must complete before this step
                "successors": [],    # List of step IDs that depend on this step
                "conditional_successors": [],  # List of (successor_id, condition) tuples
                "step": step
            }
        
        # Add connections to the graph
        for connection in connections:
            from_step = connection.get("from")
            to_step = connection.get("to")
            condition = connection.get("condition")  # Optional condition for branching
            
            if from_step and to_step:
                if condition:
                    # This is a conditional connection
                    if from_step in graph:
                        graph[from_step]["conditional_successors"].append({
                            "step_id": to_step,
                            "condition": condition
                        })
                    
                    # Still add as predecessor, but evaluation happens at runtime
                    if to_step in graph:
                        graph[to_step]["predecessors"].append(from_step)
                else:
                    # This is an unconditional connection
                    if from_step in graph:
                        graph[from_step]["successors"].append(to_step)
                    
                    if to_step in graph:
                        graph[to_step]["predecessors"].append(from_step)
        
        # For backward compatibility: if no explicit connections,
        # assume steps are executed in order they appear in the list
        if not connections:
            for i in range(len(steps) - 1):
                current_step = steps[i].get("id")
                next_step = steps[i + 1].get("id")
                
                if current_step and next_step:
                    # Current step has next step as successor
                    if current_step in graph:
                        graph[current_step]["successors"].append(next_step)
                    
                    # Next step has current step as predecessor
                    if next_step in graph:
                        graph[next_step]["predecessors"].append(current_step)
        
        return graph
    
    async def _execute_workflow_graph(
        self, 
        execution_id: str,
        steps: List[Dict[str, Any]],
        dependency_graph: Dict[str, Dict[str, Any]],
        initial_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Execute a workflow using its dependency graph representation.
        
        Args:
            execution_id (str): ID of the current execution
            steps (List[Dict[str, Any]]): List of step definitions
            dependency_graph (Dict[str, Dict[str, Any]]): Dependency graph
            initial_input (Dict[str, Any]): Initial input data
            context (Dict[str, Any]): Current execution context
            
        Returns:
            bool: True if workflow executed successfully, False otherwise
        """
        # Track completed steps and their outputs
        completed_steps = set()
        step_outputs = {}
        
        # Track steps that should be skipped (branches not taken)
        skipped_steps = set()
        
        # Initialize with the initial input
        step_outputs["__initial__"] = initial_input
        
        # Find steps with no predecessors (entry points) or whose predecessors are all completed
        async def get_next_steps() -> List[str]:
            next_steps = []
            for step_id, data in dependency_graph.items():
                # Skip already completed or skipped steps
                if step_id in completed_steps or step_id in skipped_steps:
                    continue
                    
                # Check if all predecessors are completed
                preds = data["predecessors"]
                if not preds or all(pred in completed_steps for pred in preds):
                    # For steps with predecessors, check if they should be executed based on branch conditions
                    should_execute = True
                    
                    # If this step has predecessors, check if it's part of a branch condition
                    if preds:
                        # Check each predecessor to see if this step should be executed
                        # based on the branch taken from that predecessor
                        for pred_id in preds:
                            pred_data = dependency_graph.get(pred_id, {})
                            
                            # Check if this predecessor has conditional successors
                            if "conditional_successors" in pred_data and pred_data["conditional_successors"]:
                                # Get the branch taken from this predecessor (if any)
                                pred_output = step_outputs.get(pred_id, {})
                                branch_taken = pred_output.get("branch")
                                
                                # If no branch specified in the output, default to "default"
                                if branch_taken is None:
                                    branch_taken = "default"
                                
                                # Check if this step is in the branch that was taken
                                is_in_branch = False
                                for succ in pred_data["conditional_successors"]:
                                    if (succ["step_id"] == step_id and 
                                        (succ["condition"] == branch_taken or succ["condition"] == "*")):
                                        is_in_branch = True
                                        break
                                
                                # If this predecessor has conditional successors but this step
                                # is not in the branch that was taken, it should be skipped
                                if not is_in_branch:
                                    # Only skip if the predecessor didn't list this step
                                    # as an unconditional successor as well
                                    if step_id not in pred_data["successors"]:
                                        should_execute = False
                                        break
                    
                    if should_execute:
                        next_steps.append(step_id)
                    else:
                        # Mark this step as skipped
                        skipped_steps.add(step_id)
                        # Log that this step was skipped due to branch condition
                        step_data = dependency_graph[step_id]["step"]
                        step_name = step_data.get("name", step_id)
                        await self._log_execution_info(
                            execution_id,
                            f"Skipping step {step_name} as branch condition not met",
                            step_id=step_id,
                            step_name=step_name,
                            metadata={"reason": "branch_condition_not_met"}
                        )
            
            return next_steps
        
        # Log workflow start
        await self._log_execution_info(
            execution_id,
            f"Starting workflow execution: {context['workflow_name']}",
            step_id="workflow_start"
        )
        
        # Execute steps in topological order (respecting dependencies)
        while True:
            # Get steps ready to be executed
            ready_steps = await get_next_steps()
            
            # If no more steps to execute, we're done
            if not ready_steps:
                break
                
            # Check if we can execute steps in parallel
            if len(ready_steps) > 1:
                await self._log_execution_info(
                    execution_id,
                    f"Executing {len(ready_steps)} steps in parallel: {', '.join(ready_steps)}",
                    step_id="parallel_execution",
                    metadata={"parallel_steps": ready_steps}
                )
                
                # Execute steps in parallel
                parallel_results = await self._execute_steps_in_parallel(
                    execution_id,
                    ready_steps,
                    dependency_graph,
                    step_outputs,
                    context
                )
                
                # Process parallel execution results
                for step_id, (success, output) in parallel_results.items():
                    # Store step result
                    step_data = dependency_graph[step_id]["step"]
                    step_name = step_data.get("name", step_id)
                    
                    context["steps_results"][step_id] = {
                        "success": success,
                        "output": output,
                        "step_id": step_id,
                        "step_name": step_name,
                        "executed_in_parallel": True,
                        "parallel_group": ready_steps
                    }
                    
                    # Check if this step defined a branch to take
                    if success and isinstance(output, dict) and "branch" in output:
                        branch_taken = output["branch"]
                        context["branches_taken"][step_id] = branch_taken
                        
                        await self._log_execution_info(
                            execution_id,
                            f"Step {step_name} selected branch: {branch_taken}",
                            step_id=step_id,
                            step_name=step_name,
                            metadata={"branch_taken": branch_taken}
                        )
                    
                    # Mark as completed and store output for successors
                    completed_steps.add(step_id)
                    if success:
                        step_outputs[step_id] = output
                    
                    # If step failed and is critical, stop workflow execution
                    if not success and step_data.get("critical", False):
                        await self._log_execution_warning(
                            execution_id,
                            f"Workflow execution stopped due to failure in critical step: {step_name}",
                            step_id=step_id,
                            step_name=step_name
                        )
                        return False
            else:
                # Execute a single step
                step_id = ready_steps[0]
                step_data = dependency_graph[step_id]["step"]
                step_name = step_data.get("name", step_id)
                
                # Get input for this step from its predecessors
                step_input = self._get_step_input(
                    step_id, 
                    dependency_graph, 
                    step_outputs, 
                    initial_input
                )
                
                # Execute the step
                success, output = await self._execute_step(
                    execution_id,
                    step_data,
                    step_input,
                    context
                )
                
                # Store step result
                context["steps_results"][step_id] = {
                    "success": success,
                    "output": output,
                    "step_id": step_id,
                    "step_name": step_name,
                    "executed_in_parallel": False
                }
                
                # Check if this step defined a branch to take
                if success and isinstance(output, dict) and "branch" in output:
                    branch_taken = output["branch"]
                    context["branches_taken"][step_id] = branch_taken
                    
                    await self._log_execution_info(
                        execution_id,
                        f"Step {step_name} selected branch: {branch_taken}",
                        step_id=step_id,
                        step_name=step_name,
                        metadata={"branch_taken": branch_taken}
                    )
                
                # Mark as completed and store output for successors
                completed_steps.add(step_id)
                if success:
                    step_outputs[step_id] = output
                
                # If step failed and is critical, stop workflow execution
                if not success and step_data.get("critical", False):
                    await self._log_execution_warning(
                        execution_id,
                        f"Workflow execution stopped due to failure in critical step: {step_name}",
                        step_id=step_id,
                        step_name=step_name
                    )
                    return False
        
        # Check if all steps were completed or skipped
        unprocessed_steps = set(dependency_graph.keys()) - completed_steps - skipped_steps
        if unprocessed_steps:
            await self._log_execution_warning(
                execution_id,
                f"Some steps were not executed: {', '.join(unprocessed_steps)}",
                step_id="workflow_complete",
                metadata={
                    "unprocessed_steps": list(unprocessed_steps),
                    "skipped_steps": list(skipped_steps)
                }
            )
            
        # Check if any executed step failed
        any_step_failed = any(
            not result.get("success", False) 
            for step_id, result in context["steps_results"].items()
            if step_id not in skipped_steps
        )
        
        return not any_step_failed
    
    def _get_step_input(
        self, 
        step_id: str, 
        dependency_graph: Dict[str, Dict[str, Any]],
        step_outputs: Dict[str, Dict[str, Any]],
        initial_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get input for a step based on outputs from its predecessors.
        
        Args:
            step_id (str): ID of the step
            dependency_graph (Dict[str, Dict[str, Any]]): Dependency graph
            step_outputs (Dict[str, Dict[str, Any]]): Outputs from completed steps
            initial_input (Dict[str, Any]): Initial input data
            
        Returns:
            Dict[str, Any]: Input data for the step
        """
        predecessors = dependency_graph[step_id]["predecessors"]
        
        # If no predecessors, use initial input
        if not predecessors:
            return initial_input
        
        # If single predecessor, use its output directly
        if len(predecessors) == 1:
            pred_id = predecessors[0]
            return step_outputs.get(pred_id, {})
        
        # If multiple predecessors, combine their outputs
        # (each under their own key to avoid collisions)
        combined_input = {}
        for pred_id in predecessors:
            if pred_id in step_outputs:
                combined_input[pred_id] = step_outputs[pred_id]
                
        return combined_input
    
    async def _execute_steps_in_parallel(
        self,
        execution_id: str,
        step_ids: List[str],
        dependency_graph: Dict[str, Dict[str, Any]],
        step_outputs: Dict[str, Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Tuple[bool, Dict[str, Any]]]:
        """
        Execute multiple workflow steps in parallel.
        
        Args:
            execution_id (str): ID of the current execution
            step_ids (List[str]): IDs of steps to execute in parallel
            dependency_graph (Dict[str, Dict[str, Any]]): Dependency graph
            step_outputs (Dict[str, Dict[str, Any]]): Outputs from completed steps
            context (Dict[str, Any]): Current execution context
            
        Returns:
            Dict[str, Tuple[bool, Dict[str, Any]]]: Dictionary mapping step IDs to tuples
                containing (success, output) for each step
        """
        # Prepare tasks for parallel execution
        tasks = []
        initial_input = step_outputs.get("__initial__", {})
        
        for step_id in step_ids:
            step_data = dependency_graph[step_id]["step"]
            
            # Get input for this step
            step_input = self._get_step_input(
                step_id, 
                dependency_graph, 
                step_outputs, 
                initial_input
            )
            
            # Create task for this step
            task = self._execute_step(execution_id, step_data, step_input, context)
            tasks.append((step_id, task))
        
        # Execute tasks in parallel and wait for all to complete
        results = {}
        
        # Use asyncio.gather to run all tasks concurrently
        tasks_dict = {step_id: task for step_id, task in tasks}
        exec_tasks = asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # Wait for all tasks to complete
        exec_results = await exec_tasks
        
        # Process results
        for i, (step_id, _) in enumerate(tasks):
            result = exec_results[i]
            
            # Handle exceptions
            if isinstance(result, Exception):
                # Log the error
                step_data = dependency_graph[step_id]["step"]
                step_name = step_data.get("name", step_id)
                
                error_msg = str(result)
                stack_trace = "".join(traceback.format_exception(
                    type(result), result, result.__traceback__
                ))
                
                await self._log_execution_error(
                    execution_id,
                    f"Error executing parallel step {step_name}: {error_msg}",
                    step_id=step_id,
                    step_name=step_name,
                    metadata={
                        "error": error_msg,
                        "stack_trace": stack_trace,
                        "parallel_execution": True
                    }
                )
                
                # Store error result
                results[step_id] = (False, {
                    "error": error_msg,
                    "stack_trace": stack_trace
                })
            else:
                # Store successful result
                success, output = result
                results[step_id] = (success, output)
        
        return results
    
    async def _execute_step(
        self, 
        execution_id: str, 
        step: Dict[str, Any], 
        step_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute a single workflow step.
        
        Args:
            execution_id (str): ID of the current execution
            step (Dict[str, Any]): Step definition from the workflow
            step_input (Dict[str, Any]): Input data for this step
            context (Dict[str, Any]): Current execution context
            
        Returns:
            Tuple[bool, Dict[str, Any]]: Tuple containing (success, output)
                where success is a boolean indicating if step executed successfully
                and output is the result of the step execution
        """
        step_id = step.get("id", "unknown_step")
        step_name = step.get("name", step_id)
        step_type = step.get("type", "unknown")
        step_config = step.get("config", {})
        
        try:
            # Log step start
            await self._log_execution_info(
                execution_id,
                f"Executing step: {step_name}",
                step_id=step_id,
                step_name=step_name,
                metadata={"step_type": step_type}
            )

            # Broadcast step start via WebSocket 
            await websocket_manager.broadcast_log(
                execution_id,
                {
                    "type": "step_started",
                    "step_id": step_id,
                    "step_name": step_name,
                    "step_type": step_type,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # Dispatch to appropriate step handler based on type
            handler = self._get_step_handler(step_type)
            if not handler:
                await self._log_execution_error(
                    execution_id,
                    f"Unknown step type: {step_type}",
                    step_id=step_id,
                    step_name=step_name
                )
                return False, {"error": f"Unknown step type: {step_type}"}
                
            # Execute the step handler
            step_result = await handler(step_input, step_config, context)
            
            # Log step completion
            await self._log_execution_info(
                execution_id,
                f"Step completed: {step_name}",
                step_id=step_id,
                step_name=step_name
            )
            
            # Broadcast step completion via WebSocket
            await websocket_manager.broadcast_log(
                execution_id,
                {
                    "type": "step_completed",
                    "step_id": step_id,
                    "step_name": step_name,
                    "step_type": step_type,
                    "output_summary": self._get_output_summary(step_result),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return True, step_result
            
        except Exception as e:
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            
            # Log the error
            await self._log_execution_error(
                execution_id,
                f"Error executing step {step_name}: {error_msg}",
                step_id=step_id,
                step_name=step_name,
                metadata={
                    "error": error_msg,
                    "stack_trace": stack_trace,
                    "step_type": step_type
                }
            )
            
            # Broadcast step error via WebSocket
            await websocket_manager.broadcast_log(
                execution_id,
                {
                    "type": "step_error",
                    "step_id": step_id,
                    "step_name": step_name,
                    "step_type": step_type,
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # Return failure with error information
            return False, {
                "error": error_msg,
                "stack_trace": stack_trace
            }
    
    def _get_step_handler(self, step_type: str) -> Optional[Callable]:
        """
        Get the appropriate handler function for a step type.
        
        Args:
            step_type (str): Type of the step to execute
            
        Returns:
            Optional[Callable]: Handler function for this step type or None if not found
        """
        # Map of step types to handler functions
        handlers = {
            "http": self._handle_http_step,
            "script": self._handle_script_step,
            "transform": self._handle_transform_step,
            "condition": self._handle_condition_step,
            "branch": self._handle_branch_step,  # Added specific handler for branch steps
            # Add more handlers as needed
        }
        
        return handlers.get(step_type)
    
    async def _handle_http_step(
        self, 
        step_input: Dict[str, Any], 
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle HTTP request step.
        
        Args:
            step_input (Dict[str, Any]): Input data for this step
            config (Dict[str, Any]): Configuration for the HTTP step
            context (Dict[str, Any]): Current execution context
            
        Returns:
            Dict[str, Any]: Result of the HTTP request
        """
        # This is a placeholder for actual HTTP request implementation
        # In a real implementation, use httpx or aiohttp to make the request
        
        # Set default branch based on status code
        status_code = 200  # Mock status code
        
        # Determine branch based on status code
        branch = "success"
        if status_code >= 400:
            branch = "error"
        elif status_code >= 300:
            branch = "redirect"
        
        # Return mock response with branch information
        return {
            "status": status_code,
            "body": {"message": "Mock HTTP response"},
            "headers": {"content-type": "application/json"},
            "branch": branch  # Include branch information
        }
    
    async def _handle_script_step(
        self, 
        step_input: Dict[str, Any], 
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle script execution step.
        
        Args:
            step_input (Dict[str, Any]): Input data for this step
            config (Dict[str, Any]): Configuration for the script step
            context (Dict[str, Any]): Current execution context
            
        Returns:
            Dict[str, Any]: Result of the script execution
        """
        # This is a placeholder for actual script execution
        # In a real implementation, use a sandboxed environment to execute the script
        
        # Mock script execution with branching
        success = True  # Mock success flag
        
        # Determine branch based on execution result
        branch = "success" if success else "failure"
        
        # Return mock response with branch information
        return {
            "result": "Mock script execution result",
            "input_received": step_input,
            "success": success,
            "branch": branch  # Include branch information
        }
    
    async def _handle_transform_step(
        self, 
        step_input: Dict[str, Any], 
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle data transformation step.
        
        Args:
            step_input (Dict[str, Any]): Input data for this step
            config (Dict[str, Any]): Configuration for the transform step
            context (Dict[str, Any]): Current execution context
            
        Returns:
            Dict[str, Any]: Transformed data
        """
        # This is a placeholder for actual data transformation logic
        # In a real implementation, apply the transformation rules defined in config
        
        # Determine branch based on transformation result
        has_data = bool(step_input)  # Mock condition
        branch = "data" if has_data else "no_data"
        
        # Return mock response with branch information
        return {
            "transformed_data": step_input,
            "transformation_applied": config.get("transformation", "none"),
            "branch": branch  # Include branch information
        }
    
    async def _handle_condition_step(
        self, 
        step_input: Dict[str, Any], 
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle conditional step.
        
        Args:
            step_input (Dict[str, Any]): Input data for this step
            config (Dict[str, Any]): Configuration for the condition step
            context (Dict[str, Any]): Current execution context
            
        Returns:
            Dict[str, Any]: Condition evaluation result
        """
        # Get condition expression and evaluate it
        condition = config.get("condition", "true")
        
        # This is a simple placeholder. In a real implementation, 
        # you would evaluate the condition based on step_input and context
        condition_result = True  # Mock result
        
        # Determine branch based on condition result
        branch = "true" if condition_result else "false"
        
        # Return result with branch information
        return {
            "condition_result": condition_result,
            "condition_evaluated": condition,
            "branch": branch  # Include branch information
        }
    
    async def _handle_branch_step(
        self, 
        step_input: Dict[str, Any], 
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle explicit branching step.
        
        Args:
            step_input (Dict[str, Any]): Input data for this step
            config (Dict[str, Any]): Configuration for the branch step
            context (Dict[str, Any]): Current execution context
            
        Returns:
            Dict[str, Any]: Branch selection result
        """
        # Get branch rules from config
        rules = config.get("rules", [])
        default_branch = config.get("default", "default")
        
        # Evaluate each rule to determine which branch to take
        selected_branch = default_branch
        
        for rule in rules:
            condition = rule.get("condition")
            branch = rule.get("branch")
            
            if not condition or not branch:
                continue
                
            # This is a simple placeholder. In a real implementation,
            # you would evaluate the condition based on step_input and context
            # For now, just use a mock evaluation
            condition_met = True  # Mock result
            
            if condition_met:
                selected_branch = branch
                break
        
        # Return result with selected branch
        return {
            "branch": selected_branch,
            "rules_evaluated": len(rules),
            "input": step_input
        }
    
    def _get_output_summary(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a sanitized summary of step output for WebSocket broadcasts.
        Removes potentially sensitive or large data.
        
        Args:
            output (Dict[str, Any]): Step output
            
        Returns:
            Dict[str, Any]: Sanitized output summary
        """
        if not isinstance(output, dict):
            return {"type": str(type(output))}
        
        # Create a copy to avoid modifying the original
        summary = {}
        
        # Include safe fields, limit size of others
        for key, value in output.items():
            # Always include branch information
            if key == "branch":
                summary[key] = value
                continue
                
            # For other fields, create a summary based on type
            if isinstance(value, dict):
                summary[key] = {"type": "object", "size": len(value)}
            elif isinstance(value, list):
                summary[key] = {"type": "array", "length": len(value)}
            elif isinstance(value, str) and len(value) > 100:
                summary[key] = f"{value[:100]}... (truncated)"
            else:
                summary[key] = value
        
        return summary
        
    async def _get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """
        Get a workflow by ID.
        
        Args:
            workflow_id (str): ID of the workflow to retrieve
            
        Returns:
            Optional[Workflow]: Workflow model instance or None if not found
        """
        # Get workflow from the database
        from sqlalchemy.future import select
        
        query = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db_session.execute(query)
        workflow = result.scalars().first()
        
        return workflow
    
    async def _update_execution_status(
        self, 
        execution_id: str, 
        status: str,
        context: Dict[str, Any]
    ) -> None:
        """
        Update the status of a workflow execution.
        
        Args:
            execution_id (str): ID of the execution to update
            status (str): New status (e.g., "running", "completed", "failed")
            context (Dict[str, Any]): Current execution context with results
        """
        from sqlalchemy.future import select
        
        # Get execution record
        query = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        result = await self.db_session.execute(query)
        execution = result.scalars().first()
        
        if not execution:
            logger.error(f"Cannot update execution status: Execution {execution_id} not found")
            return
        
        # Update execution fields
        execution.status = status
        
        if status in ["completed", "failed"]:
            execution.completed_at = datetime.utcnow()
            
            # Store execution outputs
            outputs = {}
            for step_id, step_result in context.get("steps_results", {}).items():
                if step_result.get("success", False):
                    outputs[step_id] = step_result.get("output", {})
            
            # Store branch paths taken
            if context.get("branches_taken"):
                outputs["__branches_taken__"] = context["branches_taken"]
                
            execution.execution_outputs = outputs
            
            # If failed, store error message
            if status == "failed":
                # Find the first error message
                error_message = None
                for step_result in context.get("steps_results", {}).values():
                    if not step_result.get("success", True) and "error" in step_result.get("output", {}):
                        error_message = step_result["output"]["error"]
                        break
                
                if error_message:
                    execution.error_message = error_message
        
        try:
            await self.db_session.commit()
        except Exception as e:
            logger.error(f"Error updating execution status: {str(e)}")
            await self.db_session.rollback()
            raise
    
    async def _log_execution_info(
        self, 
        execution_id: str, 
        message: str,
        step_id: Optional[str] = None,
        step_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an informational message for workflow execution.
        
        Args:
            execution_id (str): ID of the execution
            message (str): Log message
            step_id (Optional[str]): ID of the step (if applicable)
            step_name (Optional[str]): Name of the step (if applicable)
            metadata (Optional[Dict[str, Any]]): Additional metadata to log
        """
        await self._log_execution(
            execution_id, 
            "INFO", 
            message, 
            step_id, 
            step_name, 
            metadata
        )
    
    async def _log_execution_warning(
        self, 
        execution_id: str, 
        message: str,
        step_id: Optional[str] = None,
        step_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a warning message for workflow execution.
        
        Args:
            execution_id (str): ID of the execution
            message (str): Log message
            step_id (Optional[str]): ID of the step (if applicable)
            step_name (Optional[str]): Name of the step (if applicable)
            metadata (Optional[Dict[str, Any]]): Additional metadata to log
        """
        await self._log_execution(
            execution_id, 
            "WARNING", 
            message, 
            step_id, 
            step_name, 
            metadata
        )
    
    async def _log_execution_error(
        self, 
        execution_id: str, 
        message: str,
        step_id: Optional[str] = None,
        step_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an error message for workflow execution.
        
        Args:
            execution_id (str): ID of the execution
            message (str): Log message
            step_id (Optional[str]): ID of the step (if applicable)
            step_name (Optional[str]): Name of the step (if applicable)
            metadata (Optional[Dict[str, Any]]): Additional metadata to log
        """
        await self._log_execution(
            execution_id, 
            "ERROR", 
            message, 
            step_id, 
            step_name, 
            metadata
        )
    
    async def _log_execution(
        self, 
        execution_id: str, 
        level: str, 
        message: str,
        step_id: Optional[str] = None,
        step_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a message for workflow execution.
        
        Args:
            execution_id (str): ID of the execution
            level (str): Log level (INFO, WARNING, ERROR, DEBUG)
            message (str): Log message
            step_id (Optional[str]): ID of the step (if applicable)
            step_name (Optional[str]): Name of the step (if applicable)
            metadata (Optional[Dict[str, Any]]): Additional metadata to log
        """
        # Log to application logger first
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"[Execution {execution_id}] {message}")
        
        # Create log entry in database
        log_entry = ExecutionLog(
            execution_id=execution_id,
            level=level,
            message=message,
            step_id=step_id,
            step_name=step_name,
            metadata=metadata or {}
        )
        
        try:
            self.db_session.add(log_entry)
            await self.db_session.flush()
            await self.db_session.commit()
            
            # Broadcast log via WebSocket
            await websocket_manager.broadcast_log(
                execution_id,
                {
                    "type": "log",
                    "level": level,
                    "message": message,
                    "step_id": step_id,
                    "step_name": step_name,
                    "metadata": metadata,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error creating log entry: {str(e)}")
            await self.db_session.rollback()
            # We don't raise the exception here to avoid disrupting the workflow
            # due to logging errors


# Function to create a workflow engine instance with a new database session
async def create_workflow_engine() -> WorkflowEngine:
    """
    Create a new workflow engine instance with a fresh database session.
    
    Returns:
        WorkflowEngine: A new workflow engine instance
    """
    db = SessionLocal()
    return WorkflowEngine(db)

class WorkflowExecutor:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_workflow(
        self, 
        workflow_id: str, 
        execution_id: str,
        initial_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main execution entry point. Replace this body with your existing implementation.
        """
        print(f"Executing workflow {workflow_id} with execution ID {execution_id}")
        return {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "status": "started",
            "started_at": datetime.utcnow().isoformat()
        }

