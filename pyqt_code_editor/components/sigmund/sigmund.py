from ...widgets import Dock
from ... import watchdog, settings
from .editor_workspace import EditorWorkspace
from .sigmund_analyst_widget import SigmundAnalystWidget
import logging
logger = logging.getLogger(__name__)
        
        
class Sigmund(Dock):
    def __init__(self, parent, editor_panel):
        super().__init__('Sigmund', parent)
        self.setObjectName("sigmund")
        workspace = EditorWorkspace(editor_panel)
        self.sigmund_widget = SigmundAnalystWidget(
            self, editor_panel)
        self.sigmund_widget.setStyleSheet(f'font-size: {settings.font_size}pt')
        self.sigmund_widget.set_workspace_manager(workspace)
        self.setWidget(self.sigmund_widget)

    def setVisible(self, visible):
        if visible:
            logger.info('starting sigmund connector')
            self.sigmund_widget.start_server()
            watchdog.register_subprocess(self.sigmund_widget.server_pid)
        else:
            logger.info('stopping sigmund connector')
            self.sigmund_widget.stop_server()
        super().setVisible(visible)
