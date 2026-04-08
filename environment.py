# environment.py
# The brain of the whole system.
# Implements reset(), step(), and state() — the three core OpenEnv methods.
# Everything the agent does flows through this file.

from models import Action, Observation, Reward, StepResult, EnvironmentState
from tasks import Task, load_task
from graders import grade_diagnosis, grade_fix


class IncidentTriageEnvironment:

    def __init__(self):
        # These get properly set when reset() is called
        self.task: Task = None
        self.current_step: int = 0
        self.total_reward: float = 0.0
        self.done: bool = False
        self.diagnosis_submitted: bool = False
        self.fix_submitted: bool = False
        self.last_observation: Observation = None
        self.diagnosis_result: dict = None

    # ------------------------------------------------------------------
    # RESET
    # Starts a fresh episode for the given task.
    # Always call this before starting a new run.
    # ------------------------------------------------------------------

    def reset(self, task_id: str = "easy") -> Observation:
        # Load the task scenario (generates logs, sets the right answer)
        self.task = load_task(task_id)

        # Reset all episode tracking variables
        self.current_step = 0
        self.total_reward = 0.0
        self.done = False
        self.diagnosis_submitted = False
        self.fix_submitted = False
        self.diagnosis_result = None

        # Build the first observation — agent sees the task but no logs yet
        observation = Observation(
            available_services=self.task.services,
            log_content="",
            action_feedback=(
                "Episode started. You are an SRE engineer on call. "
                "Use read_log or search_logs to investigate, "
                "then submit a diagnose action when you know the root cause."
            ),
            current_step=0,
            task_id=self.task.task_id,
            task_description=self.task.description,
        )

        self.last_observation = observation
        return observation

    # ------------------------------------------------------------------
    # STEP
    # The agent sends one action. We process it and return what happened.
    # This is called repeatedly until done=True.
    # ------------------------------------------------------------------

    def step(self, action: Action) -> StepResult:

        # Don't allow actions after the episode has ended
        if self.done:
            return self._build_result(
                log_content="",
                feedback="Episode is already finished. Call reset() to start again.",
                step_reward=0.0,
                done=True,
                info={"error": "episode_already_done"},
            )

        self.current_step += 1

        # Route the action to the right handler
        if action.action_type == "read_log":
            return self._handle_read_log(action)

        elif action.action_type == "search_logs":
            return self._handle_search_logs(action)

        elif action.action_type == "diagnose":
            return self._handle_diagnose(action)

        elif action.action_type == "suggest_fix":
            return self._handle_suggest_fix(action)

        else:
            # Unknown action type — penalize slightly and tell the agent
            return self._build_result(
                log_content="",
                feedback=(
                    f"Unknown action type: '{action.action_type}'. "
                    f"Valid actions are: read_log, search_logs, diagnose, suggest_fix."
                ),
                step_reward=-0.05,
                done=False,
                info={"error": "unknown_action_type"},
            )

    # ------------------------------------------------------------------
    # STATE
    # Returns a full snapshot of the environment right now.
    # Used by external tools and the API to inspect what's happening.
    # ------------------------------------------------------------------

    def state(self) -> EnvironmentState:
        return EnvironmentState(
            task_id=self.task.task_id if self.task else "none",
            task_description=self.task.description if self.task else "",
            available_services=self.task.services if self.task else [],
            current_step=self.current_step,
            max_steps=self.task.max_steps if self.task else 0,
            is_active=not self.done,
            total_reward=round(self.total_reward, 3),
            diagnosis_submitted=self.diagnosis_submitted,
            fix_submitted=self.fix_submitted,
        )

    # ------------------------------------------------------------------
    # ACTION HANDLERS
    # Each handler below processes one type of action.
    # They all return a StepResult.
    # ------------------------------------------------------------------

    def _handle_read_log(self, action: Action) -> StepResult:
        service = action.service_name
        num_lines = action.num_lines or 20

        # Make sure the agent is asking about a real service
        if service not in self.task.logs:
            return self._build_result(
                log_content="",
                feedback=(
                    f"Service '{service}' not found. "
                    f"Available services: {self.task.services}"
                ),
                step_reward=-0.02,
                done=False,
                info={"error": "service_not_found"},
            )

        # Fetch the last N lines from that service's logs
        all_lines = self.task.logs[service]
        fetched_lines = all_lines[-num_lines:]
        log_text = "\n".join(fetched_lines)

        # Small positive reward for investigating — agent is doing the right thing
        return self._build_result(
            log_content=log_text,
            feedback=f"Read {len(fetched_lines)} lines from '{service}'.",
            step_reward=0.02,
            done=False,
            info={"service_read": service},
        )

    def _handle_search_logs(self, action: Action) -> StepResult:
        keyword = (action.keyword or "").lower()

        if not keyword:
            return self._build_result(
                log_content="",
                feedback="Please provide a keyword to search for.",
                step_reward=-0.02,
                done=False,
                info={"error": "empty_keyword"},
            )

        # Search across all services for the keyword
        matched_lines = []
        for service, lines in self.task.logs.items():
            for line in lines:
                if keyword in line.lower():
                    matched_lines.append(f"[{service}] {line}")

        if matched_lines:
            log_text = "\n".join(matched_lines)
            feedback = f"Found {len(matched_lines)} lines matching '{keyword}'."
            reward = 0.03   # slightly higher reward — search is more efficient
        else:
            log_text = ""
            feedback = f"No log lines found containing '{keyword}'."
            reward = 0.0

        return self._build_result(
            log_content=log_text,
            feedback=feedback,
            step_reward=reward,
            done=False,
            info={"keyword_searched": keyword, "matches_found": len(matched_lines)},
        )

    def _handle_diagnose(self, action: Action) -> StepResult:

        # Only allow one diagnosis per episode
        if self.diagnosis_submitted:
            return self._build_result(
                log_content="",
                feedback="You already submitted a diagnosis. Use suggest_fix next.",
                step_reward=-0.05,
                done=False,
                info={"error": "diagnosis_already_submitted"},
            )

        self.diagnosis_submitted = True

        # Run the grader to score the diagnosis
        result = grade_diagnosis(
            task=self.task,
            agent_service=action.root_cause_service or "",
            agent_error_type=action.error_type or "",
            agent_explanation=action.explanation or "",
            steps_taken=self.current_step,
        )

        self.diagnosis_result = result
        score = result["final_score"]

        # Convert the grader's 0.0–1.0 score into a meaningful step reward
        # A perfect diagnosis gives +0.8, a complete miss gives 0.0
        step_reward = score * 0.8

        # Episode ends after diagnosis (agent can optionally suggest a fix first)
        # But we keep done=False here to allow one more suggest_fix action
        feedback = (
            f"Diagnosis submitted. Score: {score:.2f}/1.0\n"
            f"Breakdown: {result['breakdown']}\n"
            f"You may now submit a suggest_fix action for bonus points, "
            f"or the episode will end at max steps."
        )

        return self._build_result(
            log_content="",
            feedback=feedback,
            step_reward=step_reward,
            done=False,
            info={"diagnosis_result": result},
        )

    def _handle_suggest_fix(self, action: Action) -> StepResult:

        # Fix only makes sense after a diagnosis
        if not self.diagnosis_submitted:
            return self._build_result(
                log_content="",
                feedback="Please submit a diagnose action before suggesting a fix.",
                step_reward=-0.05,
                done=False,
                info={"error": "no_diagnosis_yet"},
            )

        if self.fix_submitted:
            return self._build_result(
                log_content="",
                feedback="Fix already submitted. Episode is complete.",
                step_reward=0.0,
                done=True,
                info={"error": "fix_already_submitted"},
            )

        self.fix_submitted = True

        # Score the fix
        fix_result = grade_fix(task=self.task, fix_action=action.fix_action or "")
        fix_score = fix_result["fix_score"]

        # Episode ends after the fix is submitted
        feedback = (
            f"Fix submitted. Bonus score: {fix_score:.2f}\n"
            f"Reason: {fix_result['reason']}\n"
            "Episode complete."
        )

        return self._build_result(
            log_content="",
            feedback=feedback,
            step_reward=fix_score,
            done=True,
            info={"fix_result": fix_result},
        )

    # ------------------------------------------------------------------
    # HELPER — builds a StepResult cleanly without repeating code
    # ------------------------------------------------------------------

    def _build_result(
        self,
        log_content: str,
        feedback: str,
        step_reward: float,
        done: bool,
        info: dict,
    ) -> StepResult:

        # Check if we hit the step limit
        if self.current_step >= self.task.max_steps:
            done = True
            feedback += f" (Max steps {self.task.max_steps} reached — episode ending.)"

        # Apply a small penalty for each step taken to encourage efficiency
        time_penalty = -0.01
        adjusted_reward = step_reward + time_penalty

        self.total_reward += adjusted_reward
        self.done = done

        observation = Observation(
            available_services=self.task.services,
            log_content=log_content,
            action_feedback=feedback,
            current_step=self.current_step,
            task_id=self.task.task_id,
            task_description=self.task.description,
        )

        reward = Reward(
            step_reward=round(adjusted_reward, 3),
            total_reward=round(self.total_reward, 3),
            task_score=self.diagnosis_result["final_score"] if (done and self.diagnosis_result) else None,
            reason=feedback,
        )

        self.last_observation = observation

        return StepResult(
            observation=observation,
            reward=reward,
            done=done,
            info=info,
        )