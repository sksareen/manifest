"""Simple prompt enhancement for manifestation videos."""

def enhance_prompt(user_input: str) -> str:
    """Enhance user input for better AI video generation."""
    # Clean user input
    goal = user_input.strip()
    if not goal.startswith("me "):
        goal = f"me {goal}"
    
    # Simple enhancement - add cinematic direction
    enhanced = f"""Create a cinematic, inspiring 20-second video showing a person {goal}. 
The video should be uplifting, motivational, and visually stunning. 
High-quality cinematography, natural lighting, realistic movement."""
    
    return enhanced
