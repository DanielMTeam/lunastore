import importlib
import logging
import sys

logger = logging.getLogger("core")


def patch_redis_tasks_resolver() -> None:
    """Enhance django_tasks_redis task resolver to reload modules on AttributeError.

    If a task was added or modified while a worker/process is already running,
    importlib.import_module retrieves the cached module from sys.modules without
    the new attribute. Reloading the module from disk resolves the task cleanly.
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
        except AttributeError:
            if "." in task_path:
                module_path, func_name = task_path.rsplit(".", 1)
                if module_path in sys.modules:
                    try:
                        reloaded = importlib.reload(sys.modules[module_path])
                        func = getattr(reloaded, func_name)
                        if hasattr(func, "func") or callable(func):
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
            raise

    safe_resolve_task._is_patched = True
    RedisTaskBackend._resolve_task = safe_resolve_task
