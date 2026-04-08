# inference.py
# Baseline agent that runs against all 3 tasks and prints scores.
# Uses the OpenAI client — works with OpenAI, Groq, or any compatible API.
# Reads credentials from environment variables (never hardcode keys).

import os
import json
import httpx
from openai import OpenAI
from dotenv import load_dotenv

# Load API keys from the .env file
load_dotenv()

# ------------------------------------------------------------------
# CONFIGURATION
# All settings come from environment variables so the script is portable
# ------------------------------------------------------------------

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
HF_TOKEN     = os.getenv("HF_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860")

MAX_STEPS   = 15     # safety cap so the script never runs forever
TEMPERATURE = 0.2    # low temperature = more consistent, reproducible outputs

# The system prompt tells the model what it's doing
SYSTEM_PROMPT = """
You are an SRE (Site Reliability Engineer) on call.
You have access to server logs from multiple services.
Your job is to find the root cause of an ongoing incident.

You must respond with a JSON object representing ONE action. Choose from:

1. Read a service log:
   {"action_type": "read_log", "service_name": "<name>", "num_lines": 20}

2. Search all logs for a keyword:
   {"action_type": "search_logs", "keyword": "<word>"}

3. Submit your diagnosis (when you know the root cause):
   {"action_type": "diagnose", "root_cause_service": "<name>", 
    "error_type": "<type>", "explanation": "<your reasoning>"}

4. Suggest a fix (after diagnosing):
   {"action_type": "suggest_fix", "fix_action": "<what to do>"}

Always respond with valid JSON and nothing else.
""".strip()


# ------------------------------------------------------------------
# SETUP
# Initialize the OpenAI client pointing at whichever API we're using
# ------------------------------------------------------------------

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=API_BASE_URL,
)


# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------

def call_env(method: str, endpoint: str, body: dict = None) -> dict:
    """Send a request to the environment server and return the JSON response."""
    url = f"{ENV_BASE_URL}{endpoint}"
    with httpx.Client(timeout=30) as http:
        if method == "GET":
            response = http.get(url)
        else:
            response = http.post(url, json=body)
    response.raise_for_status()
    return response.json()


def ask_model(messages: list) -> str:
    """Send messages to the LLM and get back its action as a string."""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=512,
        )
        return completion.choices[0].message.content or ""
    except Exception as e:
        print(f"  Model call failed: {e}")
        # Fallback action if the model call fails
        return '{"action_type": "search_logs", "keyword": "ERROR"}'


def parse_action(response_text: str) -> dict:
    """Extract the JSON action from the model's response."""
    try:
        # Try to parse it directly first
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        # If there's extra text, try to find the JSON block inside it
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(response_text[start:end])
            except json.JSONDecodeError:
                pass
    # If all parsing fails, return a safe fallback
    return {"action_type": "search_logs", "keyword": "ERROR"}


# ------------------------------------------------------------------
# RUN ONE TASK
# Resets the environment, loops through steps, returns the final score
# ------------------------------------------------------------------

def run_task(task_id: str) -> float:
    print(f"\n{'='*60}")
    print(f"  Running task: {task_id.upper()}")
    print(f"{'='*60}")

    # Start a fresh episode
    observation = call_env("POST", "/reset", {"task_id": task_id})
    print(f"Task: {observation['task_description']}")
    print(f"Services available: {observation['available_services']}\n")

    # Build the conversation history for the model
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Task: {observation['task_description']}\n"
                f"Available services: {observation['available_services']}\n"
                "Start investigating. What is your first action?"
            ),
        },
    ]

    final_score = 0.0

    for step in range(1, MAX_STEPS + 1):
        print(f"--- Step {step} ---")

        # Ask the model what to do next
        response_text = ask_model(messages)
        action = parse_action(response_text)
        print(f"  Agent action: {json.dumps(action)}")

        # Send the action to the environment
        result = call_env("POST", "/step", action)

        reward    = result["reward"]["step_reward"]
        total     = result["reward"]["total_reward"]
        done      = result["done"]
        feedback  = result["observation"]["action_feedback"]
        log_content = result["observation"]["log_content"]

        print(f"  Feedback: {feedback[:120]}")
        print(f"  Step reward: {reward:+.3f} | Total: {total:.3f}")

        # If there's a final task score, save it
        if result["reward"].get("task_score") is not None:
            final_score = result["reward"]["task_score"]

        # Add the environment's response to the conversation so the model remembers it
        env_response = f"Feedback: {feedback}"
        if log_content:
            env_response += f"\n\nLogs:\n{log_content}"

        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user", "content": env_response})

        if done:
            print(f"\n  Episode complete!")
            break

    print(f"\n  Final task score: {final_score:.2f} / 1.00")
    return final_score


# ------------------------------------------------------------------
# MAIN — runs all 3 tasks and prints a summary
# ------------------------------------------------------------------

def main():
    print("START")
    print(f"Model: {MODEL_NAME}")
    print(f"Environment: {ENV_BASE_URL}")

    results = {}
    for task_id in ["easy", "medium", "hard"]:
        print(f"STEP task={task_id}")
        score = run_task(task_id)
        results[task_id] = score
        print(f"STEP task={task_id} score={score:.2f}")

    average = sum(results.values()) / len(results)
    print(f"END average_score={average:.2f}")