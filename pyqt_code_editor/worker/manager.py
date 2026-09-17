import logging
import time
from multiprocessing import Process, Queue
from .process import main_worker_process_function
from .. import watchdog, settings
logger = logging.getLogger(__name__)
STOP_UNUSED_INTERVAL = 10
_last_stop_unused_time = 0
_workers = {}  # pid -> {"process", "request_queue", "result_queue", "is_free"}
_stopping = {}  # pid -> same shape as _workers, but already asked to quit
suspended = False


def _close_worker_queues(w: dict):
    """Explicitly close a worker's queues to release file descriptors."""
    for q in (w["request_queue"], w["result_queue"]):
        try:
            q.close()
            q.join_thread()
        except Exception as e:
            logger.warning(f"Error closing queue: {e}")


def _cleanup_dead_workers():
    """
    Find and remove any worker processes that have died unexpectedly,
    closing their queues to release file descriptors.
    """
    dead_pids = [pid for pid, w in _workers.items()
                 if not w["process"].is_alive()]
    for pid in dead_pids:
        w = _workers.pop(pid)
        logger.info(f"Cleaning up dead worker {pid}")
        _close_worker_queues(w)
        try:
            w["process"].join(timeout=1)
        except Exception as e:
            logger.warning(f"Error joining dead worker {pid}: {e}")


def send_worker_request(**data) -> (Queue, int):
    """
    Send a request to a worker process. If a free worker is available,
    reuse it; otherwise create a new one. Return (result_queue, pid).

    The caller can poll the result_queue for responses, and once done,
    call mark_worker_as_free(pid) to release this worker for future use.

    If workers are suspended, return (None, None).
    """
    if suspended:
        return None, None
    # 1. Look for an existing free worker
    for pid, w in list(_workers.items()):
        if w["is_free"] and w["process"].is_alive():
            logger.info(f"Reusing free worker {pid} (of {len(_workers)}) for request {list(data.keys())}")
            w["is_free"] = False
            w["request_queue"].put(data)
            return w["result_queue"], pid

    # 2. If no free worker was found, create a new one.
    request_queue = Queue()
    result_queue = Queue()
    p = Process(target=main_worker_process_function,
                args=(request_queue, result_queue))
    p.start()
    pid = p.pid
    watchdog.register_subprocess(pid)

    _workers[pid] = {
        "process": p,
        "request_queue": request_queue,
        "result_queue": result_queue,
        "is_free": False,
    }

    logger.info(f"Creating new worker {pid} for request {data['action']}")
    settings_action = {'action': 'set_settings',
                       'settings': {name: value for name, value in settings}}
    request_queue.put(settings_action)
    # 3. Send the request, return the new worker's result queue and pid.
    request_queue.put(data)
    return result_queue, pid

def mark_worker_as_free(pid: int):
    """
    Mark a previously-used worker process (identified by pid)
    as free for reuse. If the worker has died, clean it up instead.
    """
    w = _workers.get(pid)
    if w is None:
        return
    if w["process"].is_alive():
        w["is_free"] = True
        logger.info(f"Marking worker {pid} as free")
    else:
        # The worker died while handling a request; clean up its resources
        logger.info(f"Worker {pid} has died; cleaning up.")
        _workers.pop(pid)
        _close_worker_queues(w)
        w["process"].join(timeout=1)

def check_worker_alive(pid: int) -> bool:
    w = _workers.get(pid)
    return w and w["process"].is_alive()

def reap_stopping_workers():
    """
    Finish cleaning up worker processes that were previously asked to quit
    (via stop_unused_workers()), but only once they have actually
    terminated. This is non-blocking: we merely check `is_alive()` for each
    stopping worker, and only `join()` (with a zero timeout, so it returns
    essentially instantly) processes that have already exited. Workers that
    haven't exited yet are left in place and will be picked up on a later
    call.

    This should be called periodically (e.g. from the same timer that calls
    stop_unused_workers()) so that workers asked to stop are eventually
    cleaned up and their queues closed.
    """
    done_pids = [pid for pid, w in _stopping.items() if not w["process"].is_alive()]
    for pid in done_pids:
        w = _stopping.pop(pid)
        logger.info(f"Reaping stopped worker {pid}.")
        try:
            w["process"].join(timeout=0)
        except Exception as e:
            logger.warning(f"Error joining stopped worker {pid}: {e}")
        _close_worker_queues(w)

def stop_unused_workers(max_free: int = 1, force: bool = False):
    """
    Request that free worker processes stop until there is at most
    'max_free' free processes left. This keeps us from accumulating too
    many idle worker processes. Also prunes any workers that have died
    unexpectedly.

    Important: this function never blocks waiting for a worker to actually
    exit. Workers that we decide to stop are sent a "quit" message and
    moved into an internal `_stopping` bookkeeping dict; they are only
    joined (and their queues closed) once they have actually terminated,
    which is handled by reap_stopping_workers(). This matters because
    joining a process that hasn't exited yet can block for a noticeable
    amount of time, especially on Windows, and this function is typically
    called from a periodic timer on the main/GUI thread.
    """
    global _last_stop_unused_time
    if not force and time.time() - _last_stop_unused_time < STOP_UNUSED_INTERVAL:
        return
    _last_stop_unused_time = time.time()
    # Prune dead workers first, so they don't count as free workers below
    _cleanup_dead_workers()
    # Gather a list of free worker PIDs
    free_pids = [pid for pid, w in _workers.items() if w["is_free"] and w["process"].is_alive()]
    logger.info(f"stop_unused_workers called: max_free={max_free}, found {len(free_pids)} free workers")

    # Determine how many we need to stop
    to_stop = len(free_pids) - max_free
    if to_stop <= 0:
        logger.info("No free workers to stop.")
        return

    # Ask some free workers to stop until we have max_free left. We don't
    # wait for them to exit here; see reap_stopping_workers().
    while to_stop > 0 and free_pids:
        pid = free_pids.pop()
        w = _workers.pop(pid)
        logger.info(f"Asking free worker {pid} to stop because we have too many.")
        w["request_queue"].put({"action": "quit"})
        _stopping[pid] = w
        to_stop -= 1

    logger.info("Finished requesting unused workers to stop.")

def stop_all_workers():
    """
    Cleanly shut down all worker processes. Unlike stop_unused_workers(),
    this function blocks until every worker has actually exited, since it
    is only used when we need a hard guarantee that no worker processes
    remain (e.g. on application shutdown or when suspending).
    """
    logger.info(f"Stopping {len(_workers)} worker processes...")
    for pid, w in list(_workers.items()):
        if w["process"].is_alive():
            logger.info(f"Stopping worker {pid}.")
            w["request_queue"].put({"action": "quit"})
            w["process"].join()
        _close_worker_queues(w)
        del _workers[pid]
    # Also finish off any workers that were previously asked to stop (via
    # stop_unused_workers()) but haven't been reaped yet.
    for pid, w in list(_stopping.items()):
        logger.info(f"Joining previously-stopping worker {pid}.")
        try:
            w["process"].join()
        except Exception as e:
            logger.warning(f"Error joining stopping worker {pid}: {e}")
        _close_worker_queues(w)
        del _stopping[pid]
    logger.info("All workers stopped.")


def update_setting(name, value):
    settings_action = {'action': 'set_settings', 'settings': {name: value}}
    # Send to all workers
    for pid, w in _workers.items():
        if w["process"].is_alive():
            w["request_queue"].put(settings_action)            


def suspend():
    """Stops all worker processes and ignores all requests until resume() is 
    called.
    """
    global suspended
    suspended = True
    logger.info("Suspending worker processes...")
    stop_all_workers()


def resume():
    """Resumes accepting requests."""
    global suspended
    suspended = False
    logger.info("Resuming worker processes...")


settings.setting_changed.connect(update_setting)
