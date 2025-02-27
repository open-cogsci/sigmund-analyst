import subprocess
import tempfile
import json
import os
import logging
logger = logging.getLogger(__name__)


def ruff_check(code: str) -> list[dict]:
    """
    Lints Python source code using Ruff.
    
    Args:
        code (str): The Python source code to lint.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as tmp_file:
        tmp_file.write(code)
        tmp_file_path = tmp_file.name
    print(tmp_file.name)
    cmd = ["ruff", "check", tmp_file_path, "--output-format", "json"]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
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
        row = message['location']['row']
        if row not in formatted_result:
            formatted_result[row] = []
        formatted_result[row].append({
            'code': message['code'],
            'message': message['message'],
        })
    return formatted_result
