import subprocess
import tempfile
import json
import os
import sys
import logging
logger = logging.getLogger(__name__)


def ruff_check(code: str, prefix: str | None = None) -> list[dict]:
    """
    Lints Python source code using Ruff.

    Args:
        code (str): The Python source code to lint.
    """
    if prefix:
        if not prefix.endswith('\n'):
            prefix += '\n'
        code = prefix + code
        prefix_line_offset = prefix.count('\n')
    else:
        prefix_line_offset = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as tmp_file:
        tmp_file.write(code)
        tmp_file_path = tmp_file.name
    cmd = ["ruff", "check", tmp_file_path, "--output-format", "json"]
    
    # Set creation flags for Windows to prevent console window from appearing
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True,
                                   creationflags=creation_flags)
        stdout, stderr = process.communicate()
    except Exception as e:
        logger.error(f'failed to invoke ruff: {e}')
        return {}
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
    try:
        result = json.loads(stdout)
    except Exception as e:
        logger.error(f'failed to parse ruff output: {e}')
        return {}
    formatted_result = {}
    for message in result:
        row = message['location']['row'] - prefix_line_offset
        if row not in formatted_result:
            formatted_result[row] = []
        formatted_result[row].append({
            'code': message['code'],
            'message': message['message'],
        })
    return formatted_result