import logging
from .. import settings

logger = logging.getLogger(__name__)
client = None


def codestral_complete(code: str, cursor_pos: int, path: str | None,
                       multiline: bool = False) -> list[str]:
    global client

    if not settings.codestral_api_key:
        return []

    if client is None:
        from mistralai import Mistral
        client = Mistral(api_key=settings.codestral_api_key)

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
        top_p=1,
        timeout_ms=settings.codestral_timeout,
    )
    if not multiline:
        request["stop"] = "\n"

    try:
        response = client.fim.complete(**request)
    except Exception as e:
        logger.info(f"Codestral exception: {e}")
        return []

    if response.choices:
        completion = response.choices[0].message.content
        logger.info(f"Codestral completion: {completion}")
        if completion:
            return [{'completion' : completion, 'name': completion}]
        else:
            logger.info("Codestral completion: [empty]")
    else:
        logger.info("Codestral completion: [none]")

    return []
    
