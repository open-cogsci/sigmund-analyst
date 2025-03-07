"""This module implements a watchdog that ensures that subprocess are killed
when the main process is no longer alive. It does so by starting a separate
watchdog process that occasionally checks whether the main process is still
alive.

To handle unexpected crashes of the application, it periodically checks whether
the main process is still alive. When the main process has died, it first kills
all registerd subprocesses, and then shuts itself down. 

To handle clean application exist, it also listens for an explicit shutdown
signal, in which case it does the same.

In all cases, the watchdog should make sure that no subprocesses, including 
itself, stay alive after the main process has died.
"""
import multiprocessing as mp
import os
import signal
import sys
import time
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


# Global variables
_main_pid = os.getpid()
logger.info(f'main process is {_main_pid}')
_watchdog_process = None
_conn = None
_registered_pids = set()
_CHECK_INTERVAL = 1.0  # seconds


def _watchdog_main(main_pid, child_conn):
    """The main function of the watchdog process."""
    
    registered_pids = set()
    
    while True:
        # Check if main process is still alive
        if not _is_process_alive(main_pid):
            logger.info("watchdog: Main process died, killing all subprocesses")
            _kill_all_processes(registered_pids)
            sys.exit(0)
        
        # Check for messages from the main process
        if child_conn.poll():
            msg = child_conn.recv()
            if msg["command"] == "shutdown":
                logger.info("watchdog: Received shutdown command")
                _kill_all_processes(registered_pids)
                sys.exit(0)
            elif msg["command"] == "register":
                pid = msg["pid"]
                if pid not in registered_pids:
                    registered_pids.add(pid)
                    logger.info(f"watchdog: Registered subprocess {pid}")
        
        time.sleep(_CHECK_INTERVAL)


def _is_process_alive(pid):
    """Check if a process with the given pid is alive."""
    try:
        # Sending signal 0 checks if process exists without affecting it
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_all_processes(pids):
    """Kill all processes with the given pids."""
    for pid in pids:
        try:
            # Try SIGTERM first
            os.kill(pid, signal.SIGTERM)
            logger.info(f"watchdog: Sent SIGTERM to {pid}")
        except OSError:
            pass
    
    # Give processes time to exit gracefully
    time.sleep(0.5)
    
    # Force kill any remaining processes
    for pid in pids:
        try:
            if _is_process_alive(pid):
                os.kill(pid, signal.SIGKILL)
                logger.info(f"watchdog: Sent SIGKILL to {pid}")
        except OSError:
            pass


def _ensure_watchdog_running():
    """Ensure that the watchdog process is running."""
    global _watchdog_process, _conn
    
    if _watchdog_process is None and _main_pid is not None:
        parent_conn, child_conn = mp.Pipe()
        _watchdog_process = mp.Process(
            target=_watchdog_main,
            args=(_main_pid, child_conn),
            name="watchdog-process"
        )
        _watchdog_process.start()
        _conn = parent_conn
        logger.info(f"watchdog: Started watchdog process with PID {_watchdog_process.pid}")


def set_main_process(pid: int):
    """Sets the main process pid. This does not yet launch the watchdog process."""
    global _main_pid
    _main_pid = pid
    
    
def register_subprocess(pid: int):
    """If no watchdog process is running, this is launched now. The pid is
    registered with the watchdog.    
    """
    global _registered_pids
    
    if _main_pid is None:
        raise RuntimeError("Main process PID not set. Call set_main_process() first.")
    
    _ensure_watchdog_running()
    _registered_pids.add(pid)
    
    # Send registration to watchdog process
    if _conn is not None:
        _conn.send({"command": "register", "pid": pid})
    

def shutdown():
    """Explicitly tell the watchdog to kill all subprocesses."""
    logger.info('shutdown')
    if _conn is not None:
        _conn.send({"command": "shutdown"})
        # Give watchdog time to process the shutdown command
        time.sleep(0.1)
