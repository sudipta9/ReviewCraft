from celery import Celery
import os

celery_app = None

if not bool(os.getenv("DOCKER")):  # if running example without docker
    celery_app = Celery(
        "worker",
        backend="redis://localhost:6379/0",
        broker="amqp://guest:guest@localhost:5672//",
    )
    celery_app.conf.task_routes = {"analyze_pr_task": "test-queue"}
else:
    celery_app = Celery(
        "worker",
        backend="redis://redis:6379/0",
        broker="amqp://guest:guest@rabbitmq:5672//",
    )
    celery_app.conf.task_routes = {"analyze_pr_task": "test-queue"}

celery_app.conf.task_track_started = True
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.include = ["app.worker.analyze_pr_task"]
