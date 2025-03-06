import importlib
from .. import utils
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

editor_module_cache = {}

    
def create_editor(path=None, language=None, *args, **kwargs):
    if language is None:
        if path is None:
            language = 'text'
        else:
            language = utils.guess_language_from_path(path)
    # Load the editor module depending on the language. We store the
    # imported module in a cache for efficiency
    if language not in editor_module_cache:
        try:
            editor_module = importlib.import_module(
                f".languages.{language}", package=__package__)
        except ImportError:
            from .languages import generic as editor_module
            logger.info(f'failed to load editor module for {language}, falling back to generic')
        else:
            logger.info(f'loaded editor module for {language}')
        editor_module_cache[language] = editor_module
    else:
        editor_module = editor_module_cache[language]
    editor = editor_module.Editor(*args, language=language, **kwargs)
    if path is not None:
        editor.open_file(path)
    return editor
