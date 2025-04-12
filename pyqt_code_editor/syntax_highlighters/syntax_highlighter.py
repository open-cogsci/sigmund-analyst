import importlib
import logging
from pygments.lexers import get_lexer_by_name
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)
module_cache = {}

# Some lexers have weird names that are not recognized by get_lexer_by_name().
# Often this seems to be a matter of discarding a suffix after a space or /
# This may not be a foolproof solution.
LANGUAGE_SEPARATORS = ' ', '/'
    
def create_syntax_highlighter(language, *args, **kwargs):
    for ch in LANGUAGE_SEPARATORS:
        if ch in language:
            logger.info(f'mapping {language} to {language[:language.find(ch)]}')
            language = language[:language.find(ch)]
    try:        
        lexer = get_lexer_by_name(language)
    except Exception:
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
