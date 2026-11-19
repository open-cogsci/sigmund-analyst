import os
from qtpy.QtWidgets import QFileDialog
from mcp_relay.agent import InProcessServerProvider, RelayWidget
import logging
from .servers.mcp_sigmund_analyst import make_mcp as make_mcp_sigmund_analyst
from .servers.mcp_filesystem import make_mcp as make_mcp_filesystem
from ... import settings
logger = logging.getLogger(__name__)


def pick_fs_root() -> str:
    """Ask the user which folder the 'files' server may access.

    Runs on the GUI thread: the args_provider below is invoked on the
    agent's asyncio thread when a session opens, and call_on_gui_thread
    marshals the dialog there. Raising here fails just that one session
    with a 'closed' frame.
    """
    path = QFileDialog.getExistingDirectory(
        None, "Choose a folder that Sigmund is allowed to use",
        settings.current_folder)
    if not path:
        raise RuntimeError("no folder selected; cancelling this session")
    return path


class SigmundMCPRelayWidget(RelayWidget):
    
    def __init__(self, parent, editor_panel):
        self._editor_panel = editor_panel        
        super().__init__(parent,
              relay_url=settings.sigmund_mcp_relay_url,
              providers=self.providers())

    def providers(self):
        providers = {
            "sigmund-analyst": InProcessServerProvider(
                "sigmund-analyst",
                make_mcp_sigmund_analyst(self._editor_panel),
                display_name="Execute code",
                enabled=False
            ),
            "files": InProcessServerProvider(
                "files",
                make_mcp_filesystem,
                args_provider=pick_fs_root,
                display_name="Access files and folders",
                enabled=False
            )
        }
        return providers
