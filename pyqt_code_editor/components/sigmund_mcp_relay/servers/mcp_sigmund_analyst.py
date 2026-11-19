"""In-process MCP server that lets a remote MCP client (through the Sigmund
MCP relay) execute Python and shell code in Sigmund Analyst.

This copies the execution semantics of
``components/sigmund/sigmund_analyst_widget.py`` (Python via the Jupyter
console, shell via ``subprocess``, working directory = the current project
folder, optional user confirmation), but exposes them as MCP tools instead of
Sigmund chat commands.

Threading: the in-process MCP server runs on the relay agent's QThread, while
the Jupyter console and the confirmation dialog live on the GUI thread. All
GUI interaction is therefore marshalled through ``_ExecutionBridge``, a QObject
that lives on the GUI thread; the tool thread blocks on a ``threading.Event``
until the result is ready.
"""

import asyncio
import os
import subprocess
import threading
import time
import logging

from qtpy.QtCore import QObject, QEventLoop, QTimer, QThread, Signal
from qtpy.QtWidgets import QDialog
from mcp_relay.agent import MCPServer

from .... import settings
from ...sigmund.confirm_run_code_dialog import ConfirmRunCodeDialog

logger = logging.getLogger(__name__)

ACTION_CANCELLED = 'I do not approve this action.'
EXECUTION_TIMEOUT = 5 * 60  # seconds; same as the Sigmund chat widget


def _working_directory():
    """The current working directory, based on the current project folder.
    Falls back to os.getcwd() if no folder is set.
    """
    folder = settings.current_folder
    return folder if folder is not None else os.getcwd()


class _ExecutionBridge(QObject):
    """Marshals code execution from the relay-agent thread to the GUI thread.

    Created on the GUI thread (``make_mcp`` is called from the widget
    constructor), so its slots always run on the GUI thread, where the
    Jupyter console and the confirmation dialog may safely be used.
    """

    _python_requested = Signal(str, object)
    _confirm_requested = Signal(str, str, object)

    def __init__(self, editor_panel):
        super().__init__()
        self._editor_panel = editor_panel
        self._python_requested.connect(self._run_python)
        self._confirm_requested.connect(self._run_confirm)

    # ------------------------------------------------------------------
    # Called from the MCP tool (agent) thread; block until the GUI thread
    # has produced a result.
    # ------------------------------------------------------------------
    def execute_python(self, code):
        """Run Python code in the Jupyter console; blocks until done."""
        box = {'event': threading.Event()}
        if QThread.currentThread() == self.thread():
            self._run_python(code, box)
        else:
            self._python_requested.emit(code, box)
            box['event'].wait()
        return box['result']

    def confirm(self, code, language):
        """Ask the user for confirmation on the GUI thread; blocks until answered."""
        if not settings.sigmund_mcp_relay_review_actions:
            return True
        box = {'event': threading.Event()}
        if QThread.currentThread() == self.thread():
            self._run_confirm(code, language, box)
        else:
            self._confirm_requested.emit(code, language, box)
            box['event'].wait()
        return box['result']

    # ------------------------------------------------------------------
    # Slots: always run on the GUI thread
    # ------------------------------------------------------------------
    @property
    def _app(self):
        """The main window (owns the Jupyter console)."""
        return self._editor_panel.window()

    @property
    def _jupyter_console(self):
        return getattr(self._app, '_jupyter_console', None)

    def _run_confirm(self, code, language, box):
        dialog = ConfirmRunCodeDialog(self._app, code, language)
        box['result'] = dialog.exec() == QDialog.Accepted
        box['event'].set()

    def _run_python(self, code, box):
        console = self._jupyter_console
        if console is None:
            box['result'] = 'Code execution not supported: no Jupyter console found.'
            box['event'].set()
            return
        if not self.confirm(code, 'python'):
            box['result'] = ACTION_CANCELLED
            box['event'].set()
            return
        app = self._app
        if hasattr(app, '_toggle_dock_widget'):
            app._toggle_dock_widget(console, show=True)
        console.change_directory(_working_directory())
        time.sleep(.5)
        loop = QEventLoop()
        holder = {}

        def on_execution_complete(output, result):
            holder['output'] = output
            if loop.isRunning():
                loop.quit()

        console.execution_complete.connect(on_execution_complete)
        QTimer.singleShot(EXECUTION_TIMEOUT * 1000, loop.quit)  # 5min timeout
        try:
            console.execute_code(code)
            loop.exec()
        finally:
            console.execution_complete.disconnect(on_execution_complete)
        if 'output' not in holder:
            box['result'] = 'Code execution timed out or failed to return a result.'
        else:
            box['result'] = f'''The following code was executed and generated the output shown below:
<executed_code>
{code}
</executed_code>

<output>
{holder["output"]}
</output>
'''
        box['event'].set()


def make_mcp(editor_panel):
    """An MCP server that executes Python and shell code in Sigmund Analyst.

    Returns a factory (called once per relay session by
    ``InProcessServerProvider``) that builds a fresh ``MCPServer``.
    """
    # Created on the GUI thread: all GUI interaction goes through this bridge.
    bridge = _ExecutionBridge(editor_panel)

    def inner():
        server = MCPServer("sigmund_analyst")

        @server.tool()
        async def execute_python(code: str) -> str:
            """Execute Python code in Sigmund Analyst's Jupyter console.

            The code runs in the Jupyter kernel, in the current working
            directory (the current project folder), and the console output
            is returned. If action review is enabled in the settings, the
            code is first shown in a confirmation dialog.
            """
            # Offload to a worker thread: the bridge blocks until the GUI
            # thread has finished executing the code.
            return await asyncio.to_thread(bridge.execute_python, code)

        @server.tool()
        async def execute_shell(code: str, timeout: int = 30,
                                working_directory: str | None = None) -> str:
            """Execute a shell command and return its output.

            The command runs with shell=True in the given working directory,
            or in the current working directory (the current project folder)
            if none is given. stdout and stderr are returned. If action
            review is enabled in the settings, the command is first shown in
            a confirmation dialog.
            """
            if not await asyncio.to_thread(bridge.confirm, code, 'shell'):
                return ACTION_CANCELLED
            cwd = working_directory if working_directory else _working_directory()

            def run():
                return subprocess.run(
                    code,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                )

            try:
                result = await asyncio.to_thread(run)
            except subprocess.TimeoutExpired:
                return f'Shell command timed out after {timeout} seconds.'
            except Exception as e:
                return f'Failed to execute shell command: {e}'
            output = result.stdout
            if result.stderr:
                output += f'\nSTDERR:\n{result.stderr}'
            if not output.strip():
                output = '(no output)'
            return f'''The following shell command was executed:
<executed_command>
{code}
</executed_command>

<output>
{output}
</output>
'''

        return server

    return inner
