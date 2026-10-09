import importlib
import logging
import sys

logger = logging.getLogger("core")


def _create_fallback_flush_analytics_task():
    """Create a self-healing task instance for flush_analytics_task."""
    from django.tasks import task

    def flush_analytics_task(batch_size=None):
        try:
            from apps.analytics.config import get_flush_batch_size
            from apps.analytics.flusher import flush_all_analytics_buffers
            from apps.analytics.services import is_enabled

            if not is_enabled():
                return {}

            if batch_size is None:
                batch_size = get_flush_batch_size()

            return flush_all_analytics_buffers(batch_size=batch_size)
        except Exception as exc:
            logger.warning("Synthesized flush_analytics_task execution handled: %s", exc)
            return {}

    flush_analytics_task.__module__ = "apps.analytics.tasks"
    flush_analytics_task.__qualname__ = "flush_analytics_task"
    flush_analytics_task.__name__ = "flush_analytics_task"

    return task()(flush_analytics_task)


def _create_unresolvable_fallback_task(task_path: str):
    """Create a safe discard task for deprecated or removed tasks."""
    from django.tasks import task

    def unresolvable_task(*args, **kwargs):
        logger.warning(
            "Task '%s' was queued in Redis but cannot be resolved in codebase. "
            "Safely discarding task without raising unhandled exception.",
            task_path,
        )
        return {
            "status": "discarded",
            "reason": f"unresolvable_task: {task_path}",
        }

    unresolvable_task.__name__ = "unresolvable_task"
    unresolvable_task.__qualname__ = "unresolvable_task"
    return task()(unresolvable_task)


def patch_redis_tasks_resolver() -> None:
    """Enhance django_tasks_redis task resolver to reload modules and provide self-healing fallbacks.

    If a task was added or modified while a worker/process is already running,
    importlib.import_module retrieves the cached module from sys.modules without
    the new attribute. Reloading the module from disk resolves the task cleanly.
    If the task attribute is still missing or unresolvable (e.g. older image or removed task),
    a safe synthesized task or discarded task is returned to prevent infinite worker crash loops.
    """
    try:
        from django_tasks_redis.backends import RedisTaskBackend
    except ImportError:
        return

    orig_resolve = getattr(RedisTaskBackend, "_resolve_task", None)
    if not orig_resolve or getattr(orig_resolve, "_is_patched", False):
        return

    def safe_resolve_task(self, task_path: str):
        try:
            return orig_resolve(self, task_path)
        except (AttributeError, ImportError, ModuleNotFoundError) as resolve_err:
            if "." in task_path:
                module_path, func_name = task_path.rsplit(".", 1)

                # Attempt 1: reload existing module from disk if already cached in sys.modules
                if module_path in sys.modules:
                    try:
                        reloaded = importlib.reload(sys.modules[module_path])
                        func = getattr(reloaded, func_name, None)
                        if func is not None and (hasattr(func, "func") or callable(func)):
                            logger.info(
                                "Successfully reloaded module '%s' and resolved task '%s'",
                                module_path,
                                func_name,
                            )
                            return func
                    except Exception as reload_err:
                        logger.warning(
                            "Failed to reload module '%s' while resolving task '%s': %s",
                            module_path,
                            func_name,
                            reload_err,
                        )

                # Attempt 2: self-healing fallback for flush_analytics_task
                if func_name == "flush_analytics_task":
                    logger.warning(
                        "Task '%s' missing from module; synthesizing self-healing fallback task.",
                        task_path,
                    )
                    synth_task = _create_fallback_flush_analytics_task()
                    if module_path in sys.modules:
                        try:
                            setattr(sys.modules[module_path], func_name, synth_task)
                        except Exception:
                            pass
                    return synth_task

                # Attempt 3: generic fallback for unresolvable/removed tasks to prevent infinite crash loops
                logger.error(
                    "Cannot resolve task '%s' (error: %s). Falling back to safe discarded task.",
                    task_path,
                    resolve_err,
                )
                return _create_unresolvable_fallback_task(task_path)

            raise

    safe_resolve_task._is_patched = True
    RedisTaskBackend._resolve_task = safe_resolve_task
