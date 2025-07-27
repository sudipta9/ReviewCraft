from celery import Celery

celery_app = None

celery_app = Celery(
    "worker",
    backend="redis://localhost:6379/0",
    broker="amqp://guest:guest@localhost:5672//",
)
celery_app.conf.task_routes = {
    "app.worker.celery_worker.pr_analysis_task": "test-queue"
}


celery_app.conf.update(task_track_started=True)
