# app/api/v1/endpoints/prompt.py

from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.prompt import OptimizePromptRequest, OptimizePromptResponse, RoutePromptRequest, RoutePromptResponse
from app.api.deps import get_current_user
from openai import AsyncOpenAI
from app.core.config import settings

router = APIRouter()

# -- Real GPT-4o Optimize Prompt Function --

async def real_optimize_prompt(prompt: str) -> str:
    client = AsyncOpenAI(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an assistant that rewrites user prompts to make them extremely clear, task-focused, and structured so that another LLM can easily generate Python code to complete the task."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        top_p=1.0,
    )

    optimized_prompt = response.choices[0].message.content
    return optimized_prompt

# -- Real GPT-4o Route Prompt Function (Needs Reasoning or Not) --

async def real_route_prompt(prompt: str) -> bool:
    client = AsyncOpenAI(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a system that decides if a user task requires deep step-by-step reasoning before action. Respond ONLY with 'true' if reasoning is needed, or 'false' if immediate action is fine. No explanations."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        top_p=1.0,
    )

    reasoning_flag = response.choices[0].message.content.strip().lower()

    if "true" in reasoning_flag:
        return True
    else:
        return False

# -- Optimize Prompt API Endpoint --

@router.post("/optimize-prompt", response_model=OptimizePromptResponse, status_code=status.HTTP_200_OK)
async def optimize_prompt(
    request: OptimizePromptRequest,
    current_user=Depends(get_current_user)
) -> OptimizePromptResponse:
    """
    Optimize a raw user prompt for clarity, task-focus, and completeness.
    """
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty."
        )

    try:
        optimized = await real_optimize_prompt(request.prompt)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to optimize prompt: {str(e)}"
        )

    return OptimizePromptResponse(
        original_prompt=request.prompt,
        optimized_prompt=optimized
    )

# -- Route Prompt API Endpoint --

@router.post("/route-prompt", response_model=RoutePromptResponse, status_code=status.HTTP_200_OK)
async def route_prompt(
    request: RoutePromptRequest,
    current_user=Depends(get_current_user)
) -> RoutePromptResponse:
    """
    Classify a prompt as needing Reasoning vs Task-only using GPT-4o.
    """

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty."
        )

    try:
        needs_reasoning = await real_route_prompt(request.prompt)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to route prompt: {str(e)}"
        )

    return RoutePromptResponse(
        prompt=request.prompt,
        needs_reasoning=needs_reasoning
    )
