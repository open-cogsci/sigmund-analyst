from ...widgets import Dock
from .sigmund_mcp_relay_widget import SigmundMCPRelayWidget
import logging
logger = logging.getLogger(__name__)
        
        
class SigmundMCPRelay(Dock):
    def __init__(self, parent, editor_panel):
        super().__init__('Sigmund', parent)
        self.setObjectName("sigmund")
        self.sigmund_widget = SigmundMCPRelayWidget(self, editor_panel)
        self.setWidget(self.sigmund_widget)
