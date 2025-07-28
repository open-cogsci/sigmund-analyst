import logging
import importlib
from . import settings
import queue
logger = logging.getLogger(__name__)
worker_functions_cache = {}


def main_worker_process_function(request_queue, result_queue):
    """
    Main worker process for handling editor backend requests.
    
    Runs in a separate process, continuously processing requests from a queue
    and sending results back through another queue. Supports code completion,
    calltips, symbol extraction, code checking, and settings management.
    
    Parameters
    ----------
    request_queue : multiprocessing.Queue
        Queue containing request dictionaries to process
    result_queue : multiprocessing.Queue
        Queue where results are sent back to the main process
        
    Request Format
    --------------
    Each request must be a dictionary with the following structure:
    
    Required fields:
        action : str
            The action to perform. One of: 'complete', 'calltip', 'symbols', 
            'check', 'set_settings', 'quit'
    
    Optional fields (depending on action):
        language : str, default 'text'
            Programming language for syntax-aware processing
        code : str, default ''
            Source code content to analyze
        cursor_pos : int, default 0
            Character position of cursor in the code
        path : str, optional
            File path for context-aware processing
        multiline : bool, default False
            Whether to enable multiline completion mode
        full : bool, default False
            Whether to return full completion details
        env_path : str, optional
            Path to Python environment for context
        prefix : str, optional
            Prefix string for filtering results
        settings : dict, optional
            Settings to update (only for 'set_settings' action)
    
    Response Format
    ---------------
    Results are dictionaries placed on result_queue with action-specific content:
    
    For 'complete' action:
        {
            'action': 'complete',
            'completions': list or None,
            'cursor_pos': int,
            'multiline': bool,
            'full': bool
        }
    
    For 'calltip' action:
        {
            'action': 'calltip', 
            'signatures': list or None,
            'cursor_pos': int
        }
    
    For 'symbols' action:
        {
            'action': 'symbols',
            'symbols': list
        }
    
    For 'check' action:
        {
            'action': 'check',
            'messages': dict
        }
    
    Behavior
    --------
    - Runs indefinitely until receiving a 'quit' action
    - Dynamically loads language-specific worker modules on first use
    - Caches imported worker modules for efficiency
    - Falls back to generic worker functions if language-specific module unavailable
    - Skips invalid requests (None, non-dict, or missing 'action' field)
    - Logs all major operations and errors
    - For 'set_settings' action, updates the settings module attributes directly
    - Worker modules must provide functions: complete, calltip, symbols, check
      (functions can be None if not supported for that language)
    
    Notes
    -----
    This function is designed to run in a separate process to avoid blocking
    the main editor thread during potentially slow operations like code analysis.
    Language-specific worker modules are expected to be in the 'languages' 
    subpackage.
    """
    logger.info("Started completion worker.")
    while True:
        try:
            request = request_queue.get(True, 5)
        except queue.Empty:
            continue
        if request is None:
            logger.info("Received None request (possibly legacy or invalid). Skipping.")
            continue
        # Expect a dict with at least an 'action' field
        if not isinstance(request, dict):
            logger.info(f"Invalid request type: {type(request)}. Skipping.")
            continue        
        # Most of the parameters apply to multiple actions, so we extract them
        # here.
        action = request.get('action', None)
        language = request.get('language', 'text')
        code = request.get('code', '')
        cursor_pos = request.get('cursor_pos', 0)
        path = request.get('path', None)
        multiline = request.get('multiline', False)
        full = request.get('full', False)
        env_path = request.get('env_path', None)
        prefix = request.get('prefix', None)
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
        if language not in worker_functions_cache:
            try:
                worker_functions = importlib.import_module(
                    f".languages.{language}", package=__package__)
            except ImportError:
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
                logger.info(f"Performing code completion: language='{language}', multiline={multiline}, path={path}, env_path={env_path}")
                completions = worker_functions.complete(
                    code, cursor_pos, path=path, multiline=multiline, full=full,
                    env_path=env_path, prefix=prefix)
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
                logger.info(f"Performing calltip: language='{language}', path={path}, env_path={env_path}")
                signatures = worker_functions.calltip(
                    code, cursor_pos, path=path, env_path=env_path,
                    prefix=prefix)
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
                symbols_results = []
            else:
                symbols_results = worker_functions.symbols(code)
            result_queue.put({
                'action': 'symbols',
                'symbols': symbols_results
            })
            
        elif action == 'check':
            if worker_functions.check is None:
                check_results = {}
            else:
                check_results = worker_functions.check(code, prefix=prefix)
            result_queue.put({
                'action': 'check',
                'messages': check_results
            })

    logger.info("Completion worker has shut down.")