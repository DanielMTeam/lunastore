import logging
import signal
import time

from django.core.management.base import BaseCommand
from django_tasks_redis import executor

logger = logging.getLogger("core")


class Command(BaseCommand):
    help = "Run a worker process to consume and execute background tasks from Redis"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_stop = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--queue",
            dest="queue_name",
            default=None,
            help="Process only tasks from a specific queue",
        )
        parser.add_argument(
            "--backend",
            dest="backend_name",
            default="default",
            help="Backend alias in TASKS settings (default: 'default')",
        )
        parser.add_argument(
            "--continuous",
            action="store_true",
            default=False,
            help="Run continuously in a loop without exiting when queue is empty",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=1.0,
            help="Polling interval in seconds when idle (default: 1.0)",
        )
        parser.add_argument(
            "--max-tasks",
            type=int,
            default=0,
            help="Maximum number of tasks to process before exiting (0 = unlimited)",
        )
        parser.add_argument(
            "--claim-interval",
            type=float,
            default=60.0,
            help="Interval in seconds for claiming stale/orphaned tasks (default: 60.0)",
        )

    def handle(self, *args, **options):
        queue_name = options.get("queue_name")
        backend_name = options.get("backend_name", "default")
        continuous = options.get("continuous", False)
        interval = options.get("interval", 1.0)
        max_tasks = options.get("max_tasks", 0)
        claim_interval = options.get("claim_interval", 60.0)

        # Set up signal handlers for graceful termination
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        worker_id = executor._generate_worker_id()

        self.stdout.write(
            self.style.SUCCESS(f"[*] Starting LunaStore Redis task worker: {worker_id}")
        )
        if queue_name:
            self.stdout.write(f"    Queue: {queue_name}")
        self.stdout.write(f"    Backend: {backend_name}")
        self.stdout.write(f"    Continuous: {continuous}")
        self.stdout.write(f"    Poll interval: {interval}s")

        from django.tasks import task_backends
        backend = task_backends[backend_name]
        if not hasattr(backend, "get_client"):
            self.stdout.write(
                self.style.WARNING(
                    f"Backend '{backend_name}' ({type(backend).__name__}) does not support Redis worker polling; exiting."
                )
            )
            return

        tasks_processed = 0
        last_claim_time = time.time()

        while not self.should_stop:
            current_time = time.time()
            if current_time - last_claim_time >= claim_interval:
                try:
                    claimed = executor.claim_stale_tasks(backend_name=backend_name)
                    if claimed > 0:
                        self.stdout.write(self.style.WARNING(f"Claimed {claimed} stale task(s)"))
                except Exception as e:
                    logger.warning(f"Error claiming stale tasks: {e}")
                last_claim_time = current_time

            try:
                result = executor.process_one_task(
                    queue_name=queue_name,
                    backend_name=backend_name,
                    worker_id=worker_id,
                )
            except Exception as e:
                logger.error(f"Worker task processing exception: {e}")
                result = None

            if result is not None:
                tasks_processed += 1
                status_style = (
                    self.style.SUCCESS
                    if result.status == "SUCCESSFUL"
                    else self.style.ERROR
                )
                self.stdout.write(
                    f"Processed task {result.id[:8]}: {status_style(result.status)}"
                )

                if max_tasks > 0 and tasks_processed >= max_tasks:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Reached max tasks limit ({max_tasks}), shutting down worker"
                        )
                    )
                    break
            else:
                if not continuous:
                    self.stdout.write("No tasks available in queue, exiting.")
                    break

                try:
                    time.sleep(interval)
                except KeyboardInterrupt:
                    self.should_stop = True

        self.stdout.write(
            self.style.SUCCESS(f"Worker stopped cleanly. Processed {tasks_processed} task(s).")
        )

    def _signal_handler(self, signum, frame):
        self.stdout.write(self.style.WARNING("\nShutdown signal received, finishing work..."))
        self.should_stop = True
