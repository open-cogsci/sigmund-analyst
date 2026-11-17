import os
from mcp_relay.agent import (InProcessServerProvider, RelayWidget,
                             StdioServerProvider)
import logging
from .mcp_sigmund_analyst import make_mcp
from ... import settings
logger = logging.getLogger(__name__)


class SigmundMCPRelayWidget(RelayWidget):
    
    def __init__(self, parent, editor_panel):
        self._editor_panel = editor_panel
        files_argv = ["npx", "-y", "@modelcontextprotocol/server-filesystem",
                      os.path.abspath('/home/sebastiaan/git')]
        providers = {
            "sigmund-analyst": InProcessServerProvider(
                "mcp_sigmund_analyst", make_mcp(editor_panel)),
            "files": StdioServerProvider(
                "files", files_argv),
        }
        
        super().__init__(parent,
              relay_url=settings.sigmund_mcp_relay_url,
              providers=providers)
