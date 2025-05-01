import openai

# GPT-4o call to optimize prompt
async def call_gpt_4o(system_prompt: str, user_prompt: str) -> str:
    response = await openai.ChatCompletion.acreate(
        model="gpt-4o",
        messages=[
            { "role": "system", "content": system_prompt },
            { "role": "user", "content": user_prompt }
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()

# OpenAI o3 (or similar) reasoning agent chain
async def call_openai_o3_reasoning(prompt: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "You are a senior reasoning agent. Break down user requests step-by-step and output the final clarified task for tool-calling agents."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    response = await openai.ChatCompletion.acreate(
        model="gpt-4o",  # Replace with 'gpt-4' or 'o3' if needed
        messages=messages,
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()
