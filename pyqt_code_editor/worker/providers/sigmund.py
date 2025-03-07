import os
import sys
import json
import requests
from .. import settings


def sigmund_complete(code: str, cursor_pos: int, path: str | None,
                     multiline: False) -> list[str]:
    if token is None:
        return []
    if len(code) < 10:
        return []
    ret_val = []
    start = max(0, cursor_pos - settings.sigmund_max_context)
    end = cursor_pos + settings.sigmund_max_context
    prompt = code[start: cursor_pos]
    suffix = code[cursor_pos: end]
    data = {'prompt': prompt, 'token': token, 'suffix': suffix,
            'multiline': multiline}
    try:
        response = requests.post(settings.sigmund_fim_endpoint, json=data,
                                 timeout=settings.sigmund_timeout)
        response.raise_for_status()
        resp_json = response.json()
        completion = resp_json.get('completion', '')
        return [completion]
    except Exception as e:
        return []
