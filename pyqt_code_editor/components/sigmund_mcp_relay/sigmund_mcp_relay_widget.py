import os
from qtpy.QtWidgets import QFileDialog
from mcp_relay.agent import (InProcessServerProvider, RelayWidget,
                             StdioServerProvider, call_on_gui_thread)
import logging
from .mcp_sigmund_analyst import make_mcp
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
        None, "Choose the folder the 'files' MCP server may access",
        settings.current_folder)
    if not path:
        raise RuntimeError("no folder selected; cancelling this session")
    return path


class SigmundMCPRelayWidget(RelayWidget):
    
    def __init__(self, parent, editor_panel):
        self._editor_panel = editor_panel
        files_argv = ["npx", "-y", "@modelcontextprotocol/server-filesystem",
                      os.path.abspath('/home/sebastiaan/git')]
        providers = {
            "sigmund-analyst": InProcessServerProvider(
                "sigmund-analyst",
                make_mcp(editor_panel),
                display_name="Execute code",
                enabled=False
            ),
            "files": StdioServerProvider(
                "files",
                files_argv,
                args_provider=pick_fs_root,
                display_name="Access files and folders",
                enabled=False
            )
        }
        
        super().__init__(parent,
              relay_url=settings.sigmund_mcp_relay_url,
              providers=providers)
