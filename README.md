---
title: Incident Triage OpenEnv
emoji: 🚨
colorFrom: red
colorTo: red
sdk: docker
pinned: false
license: apache-2.0
tags:
  - openenv
  - reinforcement-learning
  - sre
  - devops
  - agent
---

<<<<<<< HEAD
# 🚨 Incident Log Triage Environment
=======
## Baseline Scores

Produced by running `inference.py` with `llama-3.1-8b-instant` via Groq:

| Task   | Score      | Steps |
|--------|-----------|-------|
| Easy   | 1.00/1.00 | 5     |
| Medium | 1.00/1.00 | 5     |
| Hard   | 0.75/1.00 | 7     |
| **Average** | **0.92/1.00** | — |


# Incident Log Triage Environment
>>>>>>> 18395bb (Update README.md)

An RL environment where an agent plays the role of an on-call SRE engineer. It reads server logs, figures out what broke, and proposes a fix — across three tasks of increasing difficulty.

Built for the OpenEnv spec: the environment exposes `/reset`, `/step`, and `/state` endpoints so any agent can interact with it over HTTP.

---

## What the agent has to do

A production system is down. Multiple services are logging output, but not all of it is useful. The agent has to read through the noise, find the actual root cause, and submit a diagnosis — ideally with a fix.

Three scenarios are included:

**Easy — Single Service Crash**
One service has crashed with a clear ERROR in its logs. The agent just needs to find it and name it. Straightforward, good for sanity-checking a new agent.

**Medium — Cascading Failure**
Three services are connected. One fails first, which causes the others to fail too. The agent needs to trace back to the *original* broken service, not just report the ones that are loudly complaining.

**Hard — Silent Timeout with Red Herrings**
Five services. Two of them are logging loud, dramatic errors — but they're not the real problem. The actual failure is a quiet upstream timeout that barely shows up in the logs. The agent needs to ignore the noise and find the real cause.

---

## Observation space

At each step the agent receives:

| Field | Type | What it means |
|---|---|---|
| `available_services` | list[str] | Which services the agent can read logs from |
| `log_content` | str | The log lines returned by the last read/search action |
| `action_feedback` | str | A plain-English message about what just happened |
| `current_step` | int | How many steps have been taken so far |
| `task_id` | str | Which task is running — `easy`, `medium`, or `hard` |
| `task_description` | str | A short description of the incident scenario |

---

## Action space

The agent can take four types of actions each step:

**`read_log`** — Read recent log lines from one specific service.
```json
{"action_type": "read_log", "service_name": "auth-service", "num_lines": 20}
```

**`search_logs`** — Search across all services for a keyword.
```json
{"action_type": "search_logs", "keyword": "timeout"}
```

**`diagnose`** — Submit a diagnosis when the agent thinks it knows the root cause.
```json
{"action_type": "diagnose", "root_cause_service": "db-service", "error_type": "connection_timeout", "explanation": "The database stopped accepting connections at 03:42, causing auth and api to fail downstream."}
```

**`suggest_fix`** — Propose a fix after diagnosing.
```json
{"action_type": "suggest_fix", "fix_action": "Restart db-service and check connection pool limits."}
```

---

## Reward structure

Rewards are in the range 0.0–1.0. The agent gets partial credit for meaningful progress, not just the final answer.

- Reading relevant logs → small positive reward
- Submitting a correct diagnosis → large reward
- Correct fix after correct diagnosis → bonus reward
- Wrong diagnosis or running out of steps → penalty / zero

Each step returns `step_reward`, running `total_reward`, and a final `task_score` when the episode ends.

---

## API endpoints

The environment runs as a FastAPI server. Endpoints:

| Method | Endpoint | What it does |
|---|---|---|
| POST | `/reset` | Start a new episode. Pass `{"task_id": "easy"}` |
| POST | `/step` | Submit an action. Returns observation + reward + done flag |
| GET | `/state` | Get the current state without advancing the episode |
| GET | `/docs` | Auto-generated Swagger UI |

---

## Running locally

```bash
git clone https://huggingface.co/spaces/ThrishanthHS/incident-triage-env
cd incident-triage-env
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 7860
```

Then test it:
```bash
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_id": "easy"}'
```

### Running the baseline agent

Copy `.env.example` to `.env` and fill in your keys:
```
API_BASE_URL=https://api.groq.com/openai/v1
MODEL_NAME=llama-3.1-8b-instant
HF_TOKEN=your_hf_token_here
OPENAI_API_KEY=your_groq_key_here
ENV_BASE_URL=http://localhost:7860
```

Then run:
```bash
python inference.py
```

### Docker

```bash
docker build -t incident-triage-env .
docker run -p 7860:7860 incident-triage-env
```

---

## Baseline scores

Tested with `llama-3.1-8b-instant` via Groq:

| Task | Score | Steps taken |
|---|---|---|
| Easy | 1.00 / 1.00 | 5 |
| Medium | 1.00 / 1.00 | 5 |
| Hard | 0.75 / 1.00 | 7 |
| **Average** | **0.92 / 1.00** | — |

The hard task is the interesting one — the agent gets tripped up by the red herring errors about 25% of the time. There's room to improve with better prompting or a smarter search strategy.

---

## File structure

```
├── server.py          # FastAPI app — exposes the HTTP endpoints
├── environment.py     # Core environment logic (reset, step, state)
├── tasks.py           # The three incident scenarios
├── graders.py         # Scoring logic for each task
├── models.py          # Pydantic models for requests/responses
├── openenv.yaml       # OpenEnv spec file
├── inference.py       # Baseline agent script
├── Dockerfile
└── requirements.txt
```
