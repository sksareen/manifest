"""AI-powered prompt enhancement for manifestation videos."""

import os
import replicate

def enhance_prompt(user_input: str) -> str:
    """Enhance user input using AI text model for better video generation."""
    try:
        # Try AI enhancement first
        return _ai_enhance_prompt(user_input)
    except Exception as e:
        print(f"AI enhancement failed, using fallback: {e}")
        return _fallback_enhance_prompt(user_input)

def _ai_enhance_prompt(user_input: str) -> str:
    """Use Replicate text model to enhance the prompt."""
    text_model = os.getenv("REPLICATE_MODEL_TEXT", "deepseek-ai/deepseek-r1")
    
    system_prompt = """You are an expert at creating detailed prompts for AI video generation, specifically for manifestation and visualization videos. 

Your task: Transform a simple user goal into a detailed, cinematic video prompt that will help them visualize achieving their goal.

Guidelines:
- Keep the user's core goal exactly as stated
- Add cinematic details: camera angles, lighting, emotions, setting
- Focus on success, achievement, and positive visualization

- Make it inspiring and motivational
- Use professional cinematography language

Example:
Input: "me surfing a big wave"
Output: "Create a cinematic 20-second video of a person surfing a massive wave. Golden hour lighting, dramatic slow-motion as they ride the wave crest. Show determination and joy on their face. Professional surf cinematography with drone shots. Water spray glistening in sunlight. Triumphant success moment as they complete the ride."

Now enhance this goal:"""

    user_goal = user_input.strip()
    if not user_goal.startswith("me "):
        user_goal = f"me {user_goal}"

    input_text = f"{system_prompt}\n\nUser goal: {user_goal}\n\nEnhanced prompt:"

    output = replicate.run(
        text_model,
        input={
            "prompt": input_text,
            "max_tokens": 200,
            "temperature": 0.7
        }
    )
    
    # Extract the enhanced prompt from output
    if isinstance(output, list):
        result = ''.join(output).strip()
    else:
        result = str(output).strip()
    
    return result

def _fallback_enhance_prompt(user_input: str) -> str:
    """Fallback enhancement if AI fails."""
    goal = user_input.strip()
    if not goal.startswith("me "):
        goal = f"me {goal}"
    
    return f"""Create a cinematic, inspiring video showing a person {goal}. 
The video should be uplifting, motivational, and visually stunning. 
High-quality cinematography, natural lighting, realistic movement."""
