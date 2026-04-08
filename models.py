# models.py
from pydantic import BaseModel
from typing import Optional


class Observation(BaseModel):
    available_services: list[str]
    log_content: str = ""
    action_feedback: str = ""
    current_step: int = 0
    task_id: str = ""
    task_description: str = ""


class Action(BaseModel):
    action_type: str
    service_name: Optional[str] = None
    num_lines: Optional[int] = 20
    keyword: Optional[str] = None
    root_cause_service: Optional[str] = None
    error_type: Optional[str] = None
    explanation: Optional[str] = None
    fix_action: Optional[str] = None


class Reward(BaseModel):
    step_reward: float = 0.0
    total_reward: float = 0.0
    task_score: Optional[float] = None
    reason: str = ""


class StepResult(BaseModel):
    observation: Observation
    reward: Reward
    done: bool = False
    info: dict = {}


class EnvironmentState(BaseModel):
    task_id: str
    task_description: str
    available_services: list[str]
    current_step: int
    max_steps: int
    is_active: bool
    total_reward: float
    diagnosis_submitted: bool
    fix_submitted: bool


class ResetRequest(BaseModel):
    task_id: str = "easy"
