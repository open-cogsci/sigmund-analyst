import logging; logging.basicConfig(level=logging.INFO, force=True)
from .providers import codestral, jedi, symbol, ruff

logger = logging.getLogger(__name__)

def main_worker_process_function(request_queue, result_queue):
    """
    Runs in a separate process, handling requests in dict form.
    Supported actions include:
      - 'complete': triggers code completion
      - 'calltip': fetches calltip/signature info
      - 'setting': updates settings in the 'settings' module
      - 'quit': shuts down the worker
    """
    logger.info("Started completion worker.")
    while True:
        request = request_queue.get()
        if request is None:
            logger.info("Received None request (possibly legacy or invalid). Skipping.")
            continue

        # Expect a dict with at least an 'action' field
        if not isinstance(request, dict):
            logger.info(f"Invalid request type: {type(request)}. Skipping.")
            continue

        action = request.get('action', None)
        if action is None:
            logger.info("Request is missing 'action' field. Skipping.")
            continue

        logger.info(f"Received request action='{action}'")

        if action == 'quit':
            logger.info("Received 'quit' action. Worker will shut down.")
            break

        elif action == 'complete':
            code = request.get('code', '')
            cursor_pos = request.get('cursor_pos', 0)
            path = request.get('path', None)
            multiline = request.get('multiline', False)
            language = request.get('language', 'python')

            logger.info(f"Performing code completion: language='{language}', multiline={multiline}, path={path}")
            if language == 'python':
                completions = jedi.jedi_complete(
                    code, cursor_pos, path=path, multiline=multiline)
                if not completions:
                    codestral.last_codestral_request_cursor = None
                completions = codestral.codestral_complete(
                    code, cursor_pos, path=path, multiline=multiline) \
                        + completions
            else:
                completions = symbol.symbol_complete(
                    code, cursor_pos, path=path, multiline=multiline)
            if not completions:
                logger.info("No completions. Sending result back.")
            else:
                logger.info(f"Generated {len(completions)} completions. Sending result back.")
            result_queue.put({
                'action': 'complete',
                'completions': completions,
                'cursor_pos': cursor_pos,
                'multiline': multiline
            })

        elif action == 'calltip':
            # Similar to 'complete' but retrieves calltip info via jedi_calltip
            code = request.get('code', '')
            cursor_pos = request.get('cursor_pos', 0)
            path = request.get('path', None)
            language = request.get('language', 'python')

            logger.info(f"Performing calltip: language='{language}', path={path}")
            if language == 'python':
                signatures = jedi.jedi_signatures(code, cursor_pos, path=path)
                if signatures is None:
                    logger.info("No signatures. Sending result back.")
                else:
                    logger.info(f"Retrieved {len(signatures)} signatures.")
            else:
                signatures = []
                logger.info("Non-Python language. Returning empty calltip list.")
            result_queue.put({
                'action': 'calltip',
                'signatures': signatures,
                'cursor_pos': cursor_pos
            })

        elif action == 'setting':
            # Update some property in the 'settings' module
            name = request.get('name', None)
            value = request.get('value', None)
            logger.info(f"Updating setting: {name} = {value}")
            if name is not None:
                setattr(settings, name, value)
                
        elif action == 'check':
            code = request.get('code', '')
            language = request.get('language', 'python')
            check_results = ruff.ruff_check(code)
            result_queue.put({
                'action': 'check',
                'messages': check_results
            })

    logger.info("Completion worker has shut down.")
