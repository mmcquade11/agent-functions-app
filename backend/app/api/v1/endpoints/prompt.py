# app/api/v1/endpoints/prompt.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.prompt import OptimizePromptRequest, OptimizePromptResponse, RoutePromptRequest, RoutePromptResponse, PromptCreate, PromptResponse
from app.models.prompt import Prompt
from app.api.deps import get_current_user
from openai import AsyncOpenAI
from uuid import uuid4
from app.core.config import settings

router = APIRouter()

from openai import AsyncOpenAI
from app.core.config import settings

async def optimize_prompt(prompt: str) -> str:
    client = AsyncOpenAI(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a prompt optimizer. "
                    "Your job is to rewrite user requests into direct, structured prompts "
                    "that Claude can use to generate tool-using Python agents. "
                    "Do not explain anything, just return the rewritten prompt clearly."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        top_p=1.0,
    )

    return response.choices[0].message.content.strip()

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

@router.post("/", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def save_prompt(
    payload: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    prompt = Prompt(
        id=uuid4(),
        user_id=current_user.sub,
        original_prompt=payload.original_prompt,
        optimized_prompt=payload.optimized_prompt,
        needs_reasoning=str(payload.needs_reasoning).lower()
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt

