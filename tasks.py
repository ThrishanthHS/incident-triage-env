# tasks.py
# Defines the 3 scenarios the agent must solve.
# Each task generates realistic-looking server logs with a hidden root cause.
# The agent has to read these logs and figure out what went wrong.

import random
from dataclasses import dataclass


# ------------------------------------------------------------------
# TASK DEFINITION
# A simple container that holds everything about one task.
# ------------------------------------------------------------------

@dataclass
class Task:
    task_id: str           # "easy", "medium", or "hard"
    description: str       # plain English explanation for the agent
    services: list         # list of service names available in this scenario
    logs: dict             # dict mapping service_name -> list of log lines
    root_cause_service: str    # the correct answer — which service actually failed
    root_cause_error: str      # the correct answer — what kind of error it was
    max_steps: int         # how many steps before the episode force-ends


# ------------------------------------------------------------------
# TASK 1 — EASY
# One service crashes with a clear, obvious ERROR line.
# The agent just needs to read the right log and spot it.
# ------------------------------------------------------------------

def create_easy_task() -> Task:
    logs = {
        "auth-service": [
            "2024-01-15 10:00:01 INFO  Auth service starting up",
            "2024-01-15 10:00:02 INFO  Connected to database successfully",
            "2024-01-15 10:00:05 INFO  Listening on port 8080",
            "2024-01-15 10:01:00 INFO  User login attempt: user_id=1042",
            "2024-01-15 10:01:01 ERROR NullPointerException in TokenValidator.validate()",
            "2024-01-15 10:01:01 ERROR Cannot read field 'token' from null object",
            "2024-01-15 10:01:02 ERROR Service is shutting down due to unhandled exception",
            "2024-01-15 10:01:02 FATAL Auth service crashed. Restart required.",
        ],
        "api-gateway": [
            "2024-01-15 10:00:01 INFO  API Gateway starting up",
            "2024-01-15 10:00:03 INFO  All upstream services healthy",
            "2024-01-15 10:01:03 WARN  Upstream auth-service is not responding",
            "2024-01-15 10:01:05 INFO  Retrying connection to auth-service...",
            "2024-01-15 10:01:10 INFO  Retry 1 failed. Will retry in 5s.",
        ],
    }

    return Task(
        task_id="easy",
        description=(
            "One of your services has crashed. Read the logs from each service "
            "to find which one failed and what caused the crash. "
            "Then submit a diagnosis."
        ),
        services=list(logs.keys()),
        logs=logs,
        root_cause_service="auth-service",
        root_cause_error="NullPointerException",
        max_steps=10,
    )


# ------------------------------------------------------------------
# TASK 2 — MEDIUM
# Three services. auth-service fails first, which causes payment-service
# to fail, which causes order-service to fail. The agent needs to trace
# back to the ORIGINAL failure, not just the most obvious one.
# ------------------------------------------------------------------

def create_medium_task() -> Task:
    logs = {
        "auth-service": [
            "2024-01-15 10:00:01 INFO  Auth service starting",
            "2024-01-15 10:00:02 INFO  Database connection pool initialized",
            "2024-01-15 10:02:00 ERROR OutOfMemoryError: Java heap space",
            "2024-01-15 10:02:00 ERROR Auth service is out of memory",
            "2024-01-15 10:02:01 FATAL Process killed by OS. OOM killer activated.",
        ],
        "payment-service": [
            "2024-01-15 10:00:01 INFO  Payment service starting",
            "2024-01-15 10:00:02 INFO  Connected to auth-service",
            "2024-01-15 10:02:05 WARN  Auth service not responding — retrying",
            "2024-01-15 10:02:10 ERROR Cannot validate payment token — auth unavailable",
            "2024-01-15 10:02:11 ERROR All payment requests are now failing",
            "2024-01-15 10:02:12 FATAL Payment service entering error state",
        ],
        "order-service": [
            "2024-01-15 10:00:01 INFO  Order service starting",
            "2024-01-15 10:02:13 ERROR Payment service returned 503 Service Unavailable",
            "2024-01-15 10:02:13 ERROR Cannot complete order — payment validation failed",
            "2024-01-15 10:02:14 WARN  Order queue is backing up",
            "2024-01-15 10:02:20 FATAL Order processing has stopped completely",
        ],
    }

    return Task(
        task_id="medium",
        description=(
            "Three services are down. Each one failed because the one before it failed. "
            "Your job is to trace the chain of failures back to the FIRST service "
            "that caused everything else to break. Diagnose the root cause."
        ),
        services=list(logs.keys()),
        logs=logs,
        root_cause_service="auth-service",
        root_cause_error="OutOfMemoryError",
        max_steps=20,
    )


# ------------------------------------------------------------------
# TASK 3 — HARD
# Five services. Two services are logging loud, scary-looking errors
# that are actually harmless (red herrings). The real problem is a
# silent timeout in database-proxy that nobody is loudly complaining about.
# The agent must resist the noise and find the quiet killer.
# ------------------------------------------------------------------

def create_hard_task() -> Task:
    logs = {
        "frontend-service": [
            "2024-01-15 10:00:01 INFO  Frontend service starting",
            "2024-01-15 10:00:02 INFO  Static assets loaded successfully",
            # Loud but harmless — this is a known warning, not the real issue
            "2024-01-15 10:01:00 WARN  CSS bundle size exceeds recommended limit",
            "2024-01-15 10:01:01 WARN  Deprecated API usage detected in user-profile module",
            "2024-01-15 10:01:02 ERROR Failed to load analytics script (non-critical)",
            "2024-01-15 10:01:03 INFO  Frontend is operational. Users can still log in.",
        ],
        "auth-service": [
            "2024-01-15 10:00:01 INFO  Auth service starting",
            "2024-01-15 10:00:02 INFO  Token validation module loaded",
            "2024-01-15 10:01:00 INFO  Processing login requests normally",
            # Auth-service itself is healthy — it just can't reach the DB
            "2024-01-15 10:02:00 WARN  database-proxy response time is high: 4200ms",
            "2024-01-15 10:02:05 WARN  database-proxy response time is high: 5800ms",
            "2024-01-15 10:02:10 ERROR Request to database-proxy timed out after 6000ms",
            "2024-01-15 10:02:11 INFO  Auth service is still up but login is degraded",
        ],
        "payment-service": [
            "2024-01-15 10:00:01 INFO  Payment service starting",
            # Another red herring — these are config warnings, not the real problem
            "2024-01-15 10:00:30 WARN  SSL certificate expires in 14 days",
            "2024-01-15 10:00:31 WARN  Retry policy config is using deprecated format",
            "2024-01-15 10:01:00 INFO  Payment processing is running normally",
            "2024-01-15 10:02:12 WARN  Elevated latency detected on checkout endpoint",
        ],
        "database-proxy": [
            # This is the real culprit — but it logs almost nothing
            "2024-01-15 10:00:01 INFO  Database proxy starting",
            "2024-01-15 10:00:02 INFO  Connected to primary database",
            # Silent timeout — easy to miss if you're distracted by the red herrings
            "2024-01-15 10:01:55 WARN  Connection pool utilization at 98%",
            "2024-01-15 10:02:00 ERROR All database connections exhausted — timeout",
            "2024-01-15 10:02:01 INFO  New connection requests are queuing",
        ],
        "notification-service": [
            "2024-01-15 10:00:01 INFO  Notification service starting",
            "2024-01-15 10:00:02 INFO  Email and SMS providers connected",
            "2024-01-15 10:01:00 INFO  Processing notification queue normally",
            "2024-01-15 10:02:00 INFO  Queue depth: 42 messages pending",
            "2024-01-15 10:02:30 INFO  All notifications delivered successfully",
        ],
    }

    return Task(
        task_id="hard",
        description=(
            "Five services are showing various warnings and errors. "
            "Some of these errors are red herrings — they look scary but are not the real problem. "
            "Find the ONE service that is silently causing everything to degrade. "
            "Hint: the loudest errors are not always the most important ones."
        ),
        services=list(logs.keys()),
        logs=logs,
        root_cause_service="database-proxy",
        root_cause_error="ConnectionPoolExhausted",
        max_steps=30,
    )


# ------------------------------------------------------------------
# TASK LOADER
# Simple function that returns the right task by ID.
# Called by environment.py when reset() is triggered.
# ------------------------------------------------------------------

def load_task(task_id: str) -> Task:
    tasks = {
        "easy":   create_easy_task(),
        "medium": create_medium_task(),
        "hard":   create_hard_task(),
    }

    if task_id not in tasks:
        raise ValueError(f"Unknown task_id '{task_id}'. Choose from: easy, medium, hard")

    return tasks[task_id]