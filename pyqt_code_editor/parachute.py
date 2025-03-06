import os
import signal
import atexit
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

pids = []

@atexit.register
def shutdown():
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass  # Already dead or no permissions
        else:
            logger.info(f'brutally killed process {pid}')
