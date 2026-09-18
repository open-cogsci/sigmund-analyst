import logging
import time
from multiprocessing import Process, Queue
from .process import main_worker_process_function
from .. import watchdog, settings
logger = logging.getLogger(__name__)
STOP_UNUSED_INTERVAL = 10
MAX_CONCURRENT_STARTING = 2
_last_stop_unused_time = 0
_workers = {}  # pid -> {"process", "request_queue", "result_queue", "is_free"}
_stopping = {}  # pid -> same shape as _workers, but already asked to quit
_starting = set()  # pids of workers created but not yet proven alive-and-useful
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
        # If this worker died before ever completing its first request, it
        # was still occupying a "starting" slot; free that slot up.
        _starting.discard(pid)


def _start_new_worker(is_free: bool = False) -> int:
    """
    Create and start a single new worker process, send it the current
    settings, and register it in _workers and _starting.

    `is_free` controls whether the worker is immediately marked as
    available for reuse (used by start_worker_pool(), which starts idle
    workers ahead of time) or not (used by send_worker_request(), which
    immediately queues a real request on it).

    Returns the new worker's pid. Does not check MAX_CONCURRENT_STARTING;
    callers are responsible for that.
    """
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
        "is_free": is_free,
    }
    _starting.add(pid)

    logger.info(f"Created new worker {pid} (is_free={is_free})")
    settings_action = {'action': 'set_settings',
                       'settings': {name: value for name, value in settings}}
    request_queue.put(settings_action)
    return pid


def send_worker_request(**data) -> (Queue, int):
    """
    Send a request to a worker process. If a free worker is available,
    reuse it; otherwise create a new one. Return (result_queue, pid).

    The caller can poll the result_queue for responses, and once done,
    call mark_worker_as_free(pid) to release this worker for future use.

    If workers are suspended, return (None, None).

    We also decline to create a new worker (returning (None, None)) if
    MAX_CONCURRENT_STARTING workers are already "starting" -- i.e. have
    been created but haven't yet completed a first successful round-trip
    (see _starting / mark_worker_as_free()). This caps how many freshly
    spawned, still-booting worker processes can pile up at once. A single
    worker creation still pays the normal (and, on Windows, sometimes
    substantial) process-creation cost on the GUI thread, but we avoid the
    much worse case of several such creations happening back-to-back and
    competing for CPU/disk/antivirus scanning at the same time.

    Note that start_worker_pool() shares the same _starting bookkeeping,
    so a pool worker that is still booting also counts against this cap.
    """    
    if suspended:
        return None, None
    # 1. Look for an existing free worker. This also picks up workers that
    # were started ahead of time by start_worker_pool(), whether or not
    # they have finished booting yet.
    for pid, w in list(_workers.items()):
        if w["is_free"] and w["process"].is_alive():
            logger.info(f"Reusing free worker {pid} (of {len(_workers)}) for request {list(data.keys())}")
            w["is_free"] = False
            w["request_queue"].put(data)
            return w["result_queue"], pid

    # 2. If no free worker was found, create a new one -- unless too many
    # workers are already in the process of starting up.
    if len(_starting) >= MAX_CONCURRENT_STARTING:
        logger.info(
            f"Declining to start a new worker for request "
            f"{list(data.keys())}; {len(_starting)} worker(s) already "
            "starting."
        )
        return None, None

    pid = _start_new_worker(is_free=False)
    w = _workers[pid]
    logger.info(f"Sending request {data['action']} to newly created worker {pid}")
    w["request_queue"].put(data)
    return w["result_queue"], pid

def start_worker_pool():
    """
    Proactively start up to MAX_CONCURRENT_STARTING idle worker processes,
    so that a free (or at least already-booting) worker is more likely to
    be available by the time the user actually triggers a request -- e.g.
    right when they start typing.

    Workers started here are tracked in _starting exactly like workers
    created on-demand by send_worker_request(), and are marked as free
    immediately, so send_worker_request() will pick them up as soon as
    they exist -- whether or not they've finished booting yet.

    Intended to be called at strategic moments (e.g. app startup, after
    resume(), or when a new editor is opened), not from a tight loop: each
    call may create up to MAX_CONCURRENT_STARTING new processes on top of
    whatever is already starting.
    """
    if suspended:
        logger.info("Not starting worker pool because workers are suspended.")
        return
    for _ in range(MAX_CONCURRENT_STARTING):
        _start_new_worker(is_free=True)
    logger.info(f"Started worker pool of {MAX_CONCURRENT_STARTING} worker(s).")

def mark_worker_as_free(pid: int):
    """
    Mark a previously-used worker process (identified by pid)
    as free for reuse. If the worker has died, clean it up instead.

    This is also the point at which a worker is considered to have proven
    itself alive-and-useful (it has completed a request), so we release
    its "starting" slot here if it still held one -- whether it succeeded
    or died in the process.
    """
    w = _workers.get(pid)
    if w is None:
        return
    if w["process"].is_alive():
        w["is_free"] = True
        _starting.discard(pid)
        logger.info(f"Marking worker {pid} as free")
    else:
        # The worker died while handling a request; clean up its resources
        logger.info(f"Worker {pid} has died; cleaning up.")
        _workers.pop(pid)
        _close_worker_queues(w)
        w["process"].join(timeout=1)
        _starting.discard(pid)

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

def stop_unused_workers(max_free: int = 3, force: bool = False):
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

    Note: if max_free is set lower than MAX_CONCURRENT_STARTING, workers
    just started by start_worker_pool() may be asked to stop again before
    they ever get used. The default of 3 leaves headroom above
    MAX_CONCURRENT_STARTING (2).
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
    # Nothing is left running, so no worker can still be "starting".
    _starting.clear()
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
