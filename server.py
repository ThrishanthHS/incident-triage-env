from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
from models import Action, StepResult, EnvironmentState, Observation
from environment import IncidentTriageEnvironment

app = FastAPI(
    title="Incident Triage OpenEnv",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = IncidentTriageEnvironment()


class ResetRequest(BaseModel):
    task_id: str = "easy"


@app.get("/")
def root():
    return {
        "status": "running",
        "environment": "incident-triage-env",
        "version": "1.0.0",
        "endpoints": ["/reset", "/step", "/state", "/docs"],
    }


@app.post("/reset", response_model=Observation)
def reset(request: Optional[ResetRequest] = None):
    task_id = request.task_id if request else "easy"
    try:
        observation = env.reset(task_id=task_id)
        return observation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step", response_model=StepResult)
def step(action: Action):
    if env.task is None:
        raise HTTPException(status_code=400, detail="Call /reset first.")
    return env.step(action)


@app.get("/state", response_model=EnvironmentState)
def state():
    if env.task is None:
        raise HTTPException(status_code=400, detail="Call /reset first.")
    return env.state()