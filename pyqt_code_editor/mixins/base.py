from ..worker import manager
from qtpy.QtCore import QTimer, Signal
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class Base:
    
    code_editor_file_path = None
    code_editor_colors = None
    modification_changed = Signal(bool)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing Base")
        self.installEventFilter(self)
        # Poll timer to retrieve results from the worker
        self._cm_result_queue = None
        self._cm_worker_pid = None
        self._cm_poll_timer = QTimer(self)
        self._cm_poll_timer.setInterval(50)  # 10 times/second
        self._cm_poll_timer.timeout.connect(self._cm_check_result)
        self._cm_poll_timer.start()
        self.code_editor_line_annotations = {}
        # Single ongoing request flag, used for both completions and calltips
        self.worker_busy = False
        # Keep track of modified status
        self.modified = False
        self.modificationChanged.connect(self.set_modified)
        
    def eventFilter(self, obj, event):
        """Can be implement in other mixin classes to filter certain events,
        for example to avoid certain keypresses from being consumed.
        """
        return False        
    
    def refresh(self):
        """Can be called to indicate that the interface needs to be refreshed,
        and implement in other mixin classes to handle the actual refresh 
        logic.
        """
        pass
        
    def send_worker_request(self, **data):
        self.worker_busy = True
        self._cm_result_queue, self._cm_worker_pid = \
            manager.send_worker_request(**data)
        
    def handle_worker_result(self, action, result):
        pass
        
    def _cm_check_result(self):
        """
        Check for completion or calltip results from the external worker.
        Includes a quick check to see if the current worker is still alive.
        If not, reset our busy state and ignore any pending result queue.
        """
        # 1) Check if worker is still alive
        if self._cm_worker_pid is not None:
            alive = manager.check_worker_alive(self._cm_worker_pid)
            if not alive:
                # Worker crashed or otherwise died; reset state and return
                logger.warning("Worker process no longer alive. Resetting state.")
                self.worker_busy = False
                self._cm_result_queue = None
                self._cm_worker_pid = None
                self._cm_poll_timer.start()
                return
    
        # 2) If the worker is alive, proceed with checking the queue
        if self._cm_result_queue is None or self._cm_result_queue.empty():
            self._cm_poll_timer.start()
            return
    
        # 3) Retrieve result and reset the queue
        result = self._cm_result_queue.get()
        self._cm_result_queue = None
        manager.mark_worker_as_free(self._cm_worker_pid)
    
        # 4) Validate result
        if not isinstance(result, dict):
            logger.info(f"Got invalid response (not a dict): {result}")
            return
        try:
            action = result.pop('action')
        except KeyError:
            logger.info(f"Missing 'action' in worker response: {result}")
            return
    
        # 5) Mark ourselves as no longer busy and handle action
        self.worker_busy = False
        logger.info(f"received worker result: action={action}")
        self.handle_worker_result(action, result)
        
    def set_modified(self, modified):
        logger.info(f'modified: {modified}')
        self.document().setModified(modified)
        self.modified = modified
        self.modification_changed.emit(modified)

    def update_theme(self):
        """Mixins can implement this to update the theme in response to font changes
        etc.
        """
        pass
