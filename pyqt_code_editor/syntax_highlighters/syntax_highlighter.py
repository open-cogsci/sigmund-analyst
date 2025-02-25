import importlib
import logging
from pygments.lexers import get_lexer_by_name
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)
module_cache = {}

    
def create_syntax_highlighter(language, *args, **kwargs):
    try:
        lexer = get_lexer_by_name(language)
    except:
        lexer = get_lexer_by_name('markdown')
    if language not in module_cache:
        try:
            module = importlib.import_module(
                f".languages.{language}", package=__package__)
        except ImportError:
            from .languages import generic as module
            logger.info(f'failed to load syntax highlighter module for {language}, falling back to generic')
        else:
            logger.info(f'loaded editor module for {language}')
        module_cache[language] = module
    else:
        module = module_cache[language]        
    return module.SyntaxHighlighter(*args, lexer=lexer, **kwargs)
