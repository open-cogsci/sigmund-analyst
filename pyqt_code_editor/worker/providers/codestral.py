import os
import logging
from ... import settings

logger = logging.getLogger(__name__)
client = None
last_codestral_request_cursor = None


def codestral_complete(code: str, cursor_pos: int, path: str | None,
                       multiline: bool = False) -> list[str]:
    global client
    global last_codestral_request_cursor

    # Only call Codestral if we haven't called it recently
    if (not multiline and last_codestral_request_cursor is not None 
            and abs(cursor_pos - last_codestral_request_cursor) < 5):
        return []

    if client is None:
        from mistralai import Mistral
        client = Mistral(api_key=settings.codestral_api_key)
        import mistralai

    if len(code) < settings.codestral_min_context:
        return []

    start = max(0, cursor_pos - settings.codestral_max_context)
    end = cursor_pos + settings.codestral_max_context
    prompt = code[start: cursor_pos]
    suffix = code[cursor_pos: end]

    request = dict(
        model=settings.codestral_model,
        server_url=settings.codestral_url,
        prompt=prompt,
        suffix=suffix,
        temperature=0,
        top_p=1
    )
    if not multiline:
        request["stop"] = "\n"
        request["timeout_ms"] = settings.codestral_timeout
    else:
        request["timeout_ms"] = settings.codestral_timeout_multiline

    try:
        response = client.fim.complete(**request)
    except Exception as e:
        logger.info(f"Codestral exception: {e}")
        return []

    if response.choices:
        completion = response.choices[0].message.content
        logger.info(f"Codestral completion: {completion}")
        if completion:
            # Update our global cursor tracker only on successful requests
            last_codestral_request_cursor = cursor_pos
            return [{'completion' : completion, 'name': completion}]
        else:
            logger.info("Codestral completion: [empty]")
    else:
        logger.info("Codestral completion: [none]")

    return []
    
