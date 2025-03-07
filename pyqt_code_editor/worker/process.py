import logging
import importlib
from . import settings
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)
worker_functions_cache = {}


def main_worker_process_function(request_queue, result_queue):
    """
    Runs in a separate process, handling requests in dict form.
    Supported actions include:
      - 'complete': triggers code completion
      - 'calltip': fetches calltip/signature info
      - 'check': fetches code check/ linting info
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
        if action == 'set_settings':
            for name, value in request.get('settings', {}).items():
                setattr(settings, name, value)
            continue
        if action == 'quit':
            logger.info("Received 'quit' action. Worker will shut down.")
            break
        
        # Load the worker functions depending on the language. We store the
        # imported module in a cache for efficiency
        language = request.get('language', 'text')
        if language not in worker_functions_cache:
            try:
                worker_functions = importlib.import_module(
                    f".languages.{language}", package=__package__)
            except ImportError as e:
                from .languages import generic as worker_functions
                logger.info(f'failed to load worker functions for {language}, falling back to generic')
            else:
                logger.info(f'loaded worker functions for {language}')
            worker_functions_cache[language] = worker_functions
        else:
            worker_functions = worker_functions_cache[language]

        if action == 'complete':
            # Action not supported for language
            if worker_functions.complete is None:
                completions = None
            else:
                code = request.get('code', '')
                cursor_pos = request.get('cursor_pos', 0)
                path = request.get('path', None)
                multiline = request.get('multiline', False)
                full = request.get('full', False)
                logger.info(f"Performing code completion: language='{language}', multiline={multiline}, path={path}")
                completions = worker_functions.complete(
                    code, cursor_pos, path=path, multiline=multiline, full=full)
            if not completions:
                logger.info("No completions")
            else:
                logger.info(f"Generated {len(completions)} completions")
            result_queue.put({
                'action': 'complete',
                'completions': completions,
                'cursor_pos': cursor_pos,
                'multiline': multiline,
                'full': full
            })

        elif action == 'calltip':
            if worker_functions.calltip is None:
                signatures = None
            else:
                code = request.get('code', '')
                cursor_pos = request.get('cursor_pos', 0)
                path = request.get('path', None)
                logger.info(f"Performing calltip: language='{language}', path={path}")
                signatures = worker_functions.calltip(
                    code, cursor_pos, path=path)
            if signatures is None:
                logger.info("No calltip signatures. Sending result back.")
            else:
                logger.info(f"Retrieved {len(signatures)} calltip signatures.")
            result_queue.put({
                'action': 'calltip',
                'signatures': signatures,
                'cursor_pos': cursor_pos
            })
                
        elif action == 'symbols':
            if worker_functions.symbols is None:
                check_results = []
            else:
                code = request.get('code', '')
                symbols_results = worker_functions.symbols(code)
            result_queue.put({
                'action': 'symbols',
                'symbols': symbols_results
            })
            
        elif action == 'check':
            if worker_functions.check is None:
                check_results = {}
            else:
                code = request.get('code', '')
                check_results = worker_functions.check(code)
            result_queue.put({
                'action': 'check',
                'messages': check_results
            })

    logger.info("Completion worker has shut down.")
