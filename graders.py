# graders.py
# Scores the agent's diagnosis at the end of each episode.
# Returns a float between 0.0 (completely wrong) and 1.0 (perfect).
# Graders are deterministic — same inputs always produce the same score.

from tasks import Task


# ------------------------------------------------------------------
# MAIN GRADER
# Called when the agent submits a "diagnose" action.
# Breaks the score into three parts so the agent gets partial credit.
# ------------------------------------------------------------------

def grade_diagnosis(
    task: Task,
    agent_service: str,        # the service the agent blamed
    agent_error_type: str,     # the error type the agent identified
    agent_explanation: str,    # the agent's reasoning (checked for keywords)
    steps_taken: int,          # fewer steps = small bonus
) -> dict:

    score = 0.0
    breakdown = {}

    # ------------------------------------------------------------------
    # PART 1 — Did the agent identify the correct service? (50% of score)
    # This is the most important part. Wrong service = bad diagnosis.
    # ------------------------------------------------------------------

    if agent_service and agent_service.lower() == task.root_cause_service.lower():
        score += 0.50
        breakdown["correct_service"] = "Yes — full credit (0.50)"
    else:
        breakdown["correct_service"] = (
            f"No — agent said '{agent_service}', "
            f"correct was '{task.root_cause_service}' (0.00)"
        )

    # ------------------------------------------------------------------
    # PART 2 — Did the agent identify the correct error type? (30% of score)
    # We do a fuzzy match — the agent doesn't need to type it perfectly.
    # ------------------------------------------------------------------

    correct_error = task.root_cause_error.lower()
    agent_error = (agent_error_type or "").lower()

    # Give full credit if the agent's error type contains the key word
    # e.g. "NullPointerException" matches "nullpointer" or "null pointer"
    if correct_error in agent_error or agent_error in correct_error:
        score += 0.30
        breakdown["correct_error_type"] = "Yes — full credit (0.30)"
    else:
        breakdown["correct_error_type"] = (
            f"No — agent said '{agent_error_type}', "
            f"correct was '{task.root_cause_error}' (0.00)"
        )

    # ------------------------------------------------------------------
    # PART 3 — Does the explanation show understanding? (20% of score)
    # We check if the explanation mentions relevant keywords from the logs.
    # ------------------------------------------------------------------

    explanation = (agent_explanation or "").lower()

    # Keywords that indicate the agent actually read and understood the logs
    relevant_keywords = _get_relevant_keywords(task.task_id)
    keywords_found = [kw for kw in relevant_keywords if kw in explanation]

    if len(keywords_found) >= 2:
        score += 0.20
        breakdown["explanation_quality"] = f"Good — found keywords: {keywords_found} (0.20)"
    elif len(keywords_found) == 1:
        score += 0.10
        breakdown["explanation_quality"] = f"Partial — found only: {keywords_found} (0.10)"
    else:
        breakdown["explanation_quality"] = "Weak — no relevant keywords found (0.00)"

    # ------------------------------------------------------------------
    # EFFICIENCY BONUS — Small bonus for solving it fast (up to +0.05)
    # Doesn't push the score above 1.0.
    # ------------------------------------------------------------------

    max_steps = task.max_steps
    if steps_taken <= max_steps * 0.4:
        efficiency_bonus = 0.05
        breakdown["efficiency_bonus"] = f"Solved in {steps_taken} steps — fast! (+0.05)"
    else:
        efficiency_bonus = 0.0
        breakdown["efficiency_bonus"] = f"Solved in {steps_taken} steps — no bonus"

    final_score = min(1.0, round(score + efficiency_bonus, 2))

    return {
        "final_score": final_score,
        "breakdown": breakdown,
        "passed": final_score >= 0.5,
    }


# ------------------------------------------------------------------
# KEYWORD LOOKUP
# Returns the important words we expect in a good explanation.
# One set per task since each task has different log content.
# ------------------------------------------------------------------

def _get_relevant_keywords(task_id: str) -> list:
    keywords = {
        "easy": [
            "null", "token", "crash", "exception",
            "auth", "shutdown", "validate",
        ],
        "medium": [
            "memory", "oom", "heap", "auth", "cascade",
            "payment", "unavailable", "chain",
        ],
        "hard": [
            "timeout", "connection", "pool", "database",
            "exhausted", "proxy", "latency", "saturated",
        ],
    }
    return keywords.get(task_id, [])


# ------------------------------------------------------------------
# FIX GRADER
# Scores the agent's suggested fix after a correct diagnosis.
# This is a bonus grader — it only runs if the agent submits a fix.
# ------------------------------------------------------------------

def grade_fix(task: Task, fix_action: str) -> dict:
    fix = (fix_action or "").lower()

    # The correct fix actions we expect for each task
    good_fix_keywords = {
        "easy":   ["restart", "redeploy", "null check", "fix validator", "patch"],
        "medium": ["increase memory", "heap size", "memory limit", "scale", "jvm"],
        "hard":   ["increase pool", "connection limit", "scale database", "proxy config"],
    }

    expected = good_fix_keywords.get(task.task_id, [])
    matches = [kw for kw in expected if kw in fix]

    if len(matches) >= 1:
        return {
            "fix_score": 0.10,
            "reason": f"Good fix suggestion — matched keywords: {matches}",
        }
    else:
        return {
            "fix_score": 0.0,
            "reason": "Fix suggestion did not match expected remediation actions",
        }