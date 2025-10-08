import importlib
from .. import utils, settings
import logging
logger = logging.getLogger(__name__)

editor_module_cache = {}

# Some languages should be treated as synonyms
LANGUAGE_MAP = {
    'ipython': 'python'
}

    
def create_editor(path=None, language=None, *args, **kwargs):
    if language is None:
        if path is None:
            language = settings.default_language
        else:
            language = utils.guess_language_from_path(path)
            language = LANGUAGE_MAP.get(language, language)
    # The language is determined by the pygment lexer, and can be something like
    # javascript+genshi. This is useful for the highlighter, but for the editor
    # module we only use the main language.
    module_name = language.lower().split('+')[0]
    # Load the editor module depending on the language. We store the
    # imported module in a cache for efficiency
    if module_name not in editor_module_cache:
        try:
            editor_module = importlib.import_module(
                f".languages.{module_name}", package=__package__)
        except ImportError:
            from .languages import generic as editor_module
            logger.info(f'failed to load editor module for {module_name}, falling back to generic')
        else:
            logger.info(f'loaded editor module for {module_name}')
        editor_module_cache[module_name] = editor_module
    else:
        editor_module = editor_module_cache[module_name]
    editor = editor_module.Editor(*args, language=language, **kwargs)
    if path is not None:
        editor.open_file(path)
    return editor
