import logging; logging.basicConfig(level=logging.INFO, force=True)
from qtpy.QtWidgets import QWidget, QPlainTextEdit
from qtpy.QtCore import Qt, QRect, QPoint, QSize, QTimer
from qtpy.QtGui import QPainter, QColor, QBrush
logger = logging.getLogger(__name__)


class Check:
    """
    This is a mixin class that adds code checking / linting powers to a QPlainTextEdit.
    
    Now with a debounce mechanism so we don't request checks on every keystroke.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing Check")

        # Where lint issues will be stored once the worker returns them
        self._issues = []

        # Debounce timer: when the user stops typing for N ms, we trigger the lint action
        self._check_debounce_timer = QTimer(self)
        self._check_debounce_timer.setSingleShot(True)
        self._check_debounce_timer.setInterval(500)
        self._check_debounce_timer.timeout.connect(self._execute_check)
        # Periodic timer: also periodically run a check
        self._check_interval_timer = QTimer(self)
        self._check_interval_timer.setInterval(5000)
        self._check_interval_timer.timeout.connect(self._execute_check)

        # Connect textChanged signal to a debounced method
        self.textChanged.connect(self._on_code_changed)

    def _on_code_changed(self):
        """
        Called immediately on text changes. Rather than calling
        the worker here, we restart the debounce timer so that
        checks won't happen until the user is idle for ~500ms.
        """
        if self._check_debounce_timer.isActive():
            self._check_debounce_timer.stop()
        self._check_debounce_timer.start()

    def _execute_check(self):
        """
        Runs the actual lint check after the debounce period.
        """
        code = self.toPlainText()
        logger.info("Requesting lint check")
        self.send_worker_request(
            action='check',
            code=code,
            language=getattr(self, "code_editor_language", "python")
        )

    def handle_worker_result(self, action: str, result):
        """
        This is where we receive code-check results from the worker.
        'action' will be 'check' for lint checks. 'result' is a dict 
        with a 'messages' key that holds the issues.
        """
        super().handle_worker_result(action, result)
        if action != 'check':
            return
        # Clear all previous check annotations
        self.code_editor_line_annotations = {
            line_number: annotation for line_number, annotation
            in self.code_editor_line_annotations.items()
            if annotation['type'] != 'check'
        }
        background_color = QColor(self.code_editor_colors["highlight"])
        color = QColor(self.code_editor_colors["text"])
        for line_number, annotations in result['messages'].items():
            if not annotations:
                continue
            # There may be multiple annotations for one line. If so, we use the
            # code of the first annotation to determine the symbol.
            if annotations[0].get('code', False):
                symbol = '➜'
            else:
                symbol = '❌'
            description = '\n'.join([
                str(annotation['code']) + ': ' + annotation['message']
                for annotation in annotations
            ])
            annotation = {
                'type': 'check',
                'text': f'{symbol}{line_number}',
                'background_color': background_color,
                'color': color,
                'tooltip': description
            }
            self.code_editor_line_annotations[line_number] = annotation
        self.repaint()
