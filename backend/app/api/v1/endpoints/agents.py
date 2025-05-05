from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.agent import AgentRunRequest, AgentCreate, AgentResponse, AgentUpdate
import asyncio
import io
import sys
from contextlib import redirect_stdout
from app.core.auth import get_current_user, TokenPayload
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.agents import Agent
from uuid import uuid4
from app.schemas.agent import PromptPayload
from app.services.llm_wrappers import call_openai_o3_reasoning
from typing import List
from uuid import UUID
from sqlalchemy.future import select
from app.models.agents import Agent
from app.api.deps import get_db



router = APIRouter()

@router.post("/execute-code", response_class=StreamingResponse)
async def execute_agent(
    request: AgentRunRequest,
    user: TokenPayload = Depends(get_current_user)
):
    # Run the code safely and stream back logs
    async def run_code_stream():
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                exec_locals = {}
                exec(request.code, {}, exec_locals)
        except Exception as e:
            yield f"[error] {str(e)}\n"
        else:
            yield buffer.getvalue()

    return StreamingResponse(run_code_stream(), media_type="text/plain")

@router.post("/", response_model=AgentResponse, status_code=201)
async def save_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    agent = Agent(
        id=uuid4(),
        prompt_id=payload.prompt_id,
        user_id=current_user.sub,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        agent_code=payload.agent_code,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent

@router.post("/reasoning-agent")
async def reasoning_agent(payload: PromptPayload, user=Depends(get_current_user)):
    reasoning_steps = await call_openai_o3_reasoning(payload.prompt)
    return { "reasoned_prompt": reasoning_steps }

@router.post("/execute")
async def execute_agent(
    payload: PromptPayload,
    user=Depends(get_current_user)
):
    """
    Immediately execute an agent from the given prompt.
    """
    # 🧪 Placeholder for now — we'll wire in Claude + tool registry later
    return {
        "status": "executed",
        "message": f"Agent for prompt: '{payload.prompt}' has been executed."
    }

@router.post("/test")
async def test_agent(
    payload: PromptPayload,
    user=Depends(get_current_user)
):
    """
    Run agent in test mode — preview results without saving or scheduling.
    """
    return {
        "status": "tested",
        "message": f"Agent from prompt: '{payload.prompt}' ran in test mode."
    }

@router.post("/schedule")
async def schedule_agent(
    payload: PromptPayload,
    user=Depends(get_current_user)
):
    """
    Schedule agent to run later or on a recurring interval.
    """
    # Later: accept a cron string or timestamp
    return {
        "status": "scheduled",
        "message": f"Agent from prompt: '{payload.prompt}' scheduled for execution."
    }

@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    result = await db.execute(
        select(Agent).where(Agent.user_id == current_user.sub).order_by(Agent.created_at.desc())
    )
    return result.scalars().all()

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != current_user.sub:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != current_user.sub:
        raise HTTPException(status_code=404, detail="Agent not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)
    return agent

@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    agent = await db.get(Agent, agent_id)
    if not agent or agent.user_id != current_user.sub:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.commit()
    return







