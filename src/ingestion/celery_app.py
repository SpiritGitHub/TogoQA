"""Celery application configuration for TogoQA ingestion tasks."""

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "togoqa",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.ingestion.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Lome",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "crawl-men-daily": {
            "task": "src.ingestion.tasks.crawl_men",
            "schedule": 86400.0,  # 24h
            "options": {"queue": "crawl"},
        },
        "crawl-inseed-weekly": {
            "task": "src.ingestion.tasks.crawl_inseed",
            "schedule": 604800.0,  # 7 days
            "options": {"queue": "crawl"},
        },
        "crawl-exams-daily": {
            "task": "src.ingestion.tasks.crawl_exams",
            "schedule": 86400.0,
            "options": {"queue": "crawl"},
        },
    },
)
