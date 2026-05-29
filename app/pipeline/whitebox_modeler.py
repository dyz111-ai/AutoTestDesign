from app.core.llm_utils import chat_completion_json


def build_state_model(requirements: list) -> dict:
    """
    Uses LLM to extract a state transition model from requirements.
    Returns states, transitions (with events/guards), and initial state.
    """

    prompt = f"""
    You are a Senior Software Architect specializing in state machine modeling.

    Analyze the requirements below and build a state transition model.

    For each requirement, identify:
    - States the system can be in
    - Transitions between states (triggered by events, possibly guarded by conditions)
    - The initial state of the system

    Return STRICT JSON format:

    {{
      "states": ["Idle", "Entering Credentials", "Authenticating", "Logged In", "Locked Out"],
      "transitions": [
        {{"from": "Idle", "to": "Entering Credentials", "event": "User navigates to login"}},
        {{"from": "Entering Credentials", "to": "Authenticating", "event": "User submits credentials"}},
        {{"from": "Authenticating", "to": "Logged In", "event": "Valid credentials", "guard": "attempts < 3"}},
        {{"from": "Authenticating", "to": "Locked Out", "event": "Invalid credentials", "guard": "attempts >= 3"}}
      ],
      "initial_state": "Idle"
    }}

    Rules:
    - states must be a list of unique state names
    - transitions must include "from" and "to" fields matching state names
    - Include "event" (the trigger) for every transition
    - Include "guard" (condition) only when a transition is conditional
    - initial_state must be one of the states

    Requirements:
    {requirements}
    """

    return chat_completion_json(prompt)
