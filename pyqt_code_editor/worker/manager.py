import logging
from multiprocessing import Process, Queue
from .process import main_worker_process_function
from .. import watchdog, settings
logger = logging.getLogger(__name__)

_workers = {}  # pid -> {"process", "request_queue", "result_queue", "is_free"}


def send_worker_request(**data) -> (Queue, int):
    """
    Send a request to a worker process. If a free worker is available,
    reuse it; otherwise create a new one. Return (result_queue, pid).

    The caller can poll the result_queue for responses, and once done,
    call mark_worker_as_free(pid) to release this worker for future use.
    """
    # 1. Look for an existing free worker
    for pid, w in list(_workers.items()):
        if w["is_free"] and w["process"].is_alive():
            logger.info(f"Reusing free worker {pid} for request {list(data.keys())}")
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
    # 3. Send the request, return the new worker’s result queue and pid.
    request_queue.put(data)
    return result_queue, pid

def mark_worker_as_free(pid: int):
    """
    Mark a previously-used worker process (identified by pid)
    as free for reuse.
    """
    w = _workers.get(pid)
    if w and w["process"].is_alive():
        w["is_free"] = True
        logger.info(f"Marking worker {pid} as free")
    else:
        logger.info(f"Attempted to free worker {pid}, but it is not alive or not found.")
        
def check_worker_alive(pid: int) -> bool:
    w = _workers.get(pid)
    return w and w["process"].is_alive()

def stop_unused_workers(max_free: int = 1):
    """
    Stop free worker processes until there is at most 'max_free' free processes left.
    This keeps us from accumulating too many idle worker processes.
    """
    # Gather a list of free worker PIDs
    free_pids = [pid for pid, w in _workers.items() if w["is_free"] and w["process"].is_alive()]
    logger.info(f"stop_unused_workers called: max_free={max_free}, found {len(free_pids)} free workers")
    
    # Determine how many we need to stop
    to_stop = len(free_pids) - max_free
    if to_stop <= 0:
        logger.info("No free workers to stop.")
        return

    # Stop some free workers until we have exactly max_free left
    while to_stop > 0 and free_pids:
        pid = free_pids.pop()
        w = _workers[pid]
        logger.info(f"Stopping free worker {pid} because we have too many.")
        w["request_queue"].put({"action": "quit"})
        w["process"].join()
        del _workers[pid]
        to_stop -= 1
    
    logger.info("Finished stopping unused workers.")

def stop_all_workers():
    """
    Cleanly shut down all worker processes.
    """
    logger.info("Stopping all worker processes...")
    for pid, w in list(_workers.items()):
        if w["process"].is_alive():
            logger.info(f"Stopping worker {pid}.")
            w["request_queue"].put({"action": "quit"})
            w["process"].join()
        del _workers[pid]
    logger.info("All workers stopped.")


def update_setting(name, value):
    settings_action = {'action': 'set_settings', 'settings': {name: value}}
    # Send to all workers
    for pid, w in _workers.items():
        if w["process"].is_alive():
            w["request_queue"].put(settings_action)            
settings.setting_changed.connect(update_setting)
