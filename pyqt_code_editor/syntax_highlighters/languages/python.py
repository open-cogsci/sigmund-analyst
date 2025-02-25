from pygments.token import Token
import logging
from .generic import SyntaxHighlighter as GenericSyntaxHighlighter
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SyntaxHighlighter(GenericSyntaxHighlighter):
    """Extends the default highlighter with support for multiline strings."""
    
    def highlightBlock(self, text):
        """
        1) Determine if this line starts as 'in' or 'out' of a triple-quoted string
           from the previous block's state.
        2) Scan for triple-quote transitions, toggling in/out state.
        3) If in triple-quote mode, highlight everything as a string, else use normal
           Pygments highlighting for this line.
        4) Use self.setCurrentBlockState(...) to mark the final state for this line, so
           that QSyntaxHighlighter can handle subsequent lines correctly.
        """
    
        # old_state is typically -1 for the very first block, otherwise what we last set
        old_state = self.previousBlockState()
        previously_in_string = (old_state == 1)
        currently_in_string = previously_in_string
    
        # Search line text for triple quotes
        triple_quotes = ('"""', "'''")
        idx = 0
        while True:
            next_quote_pos = -1
            found_quote = None
            for quote in triple_quotes:
                pos = text.find(quote, idx)
                if pos != -1 and (next_quote_pos == -1 or pos < next_quote_pos):
                    next_quote_pos = pos
                    found_quote = quote
    
            if next_quote_pos == -1:
                # No more triple quotes in this line
                break
            else:
                # Toggle the multiline string state
                currently_in_string = not currently_in_string
                # Move index past the found triple quotes
                idx = next_quote_pos + len(found_quote)
    
        if currently_in_string:
            # Highlight the entire line as string
            string_format = self._get_format(Token.String)
            self.setFormat(0, len(text), string_format)
            self.setCurrentBlockState(1)
        else:
            # Use normal Pygments line-by-line highlighting
            tokens = list(self._lexer.get_tokens(text))
            index = 0
            for token_type, token_text in tokens:
                token_len = len(token_text)
                fmt = self._get_format(token_type)
                self.setFormat(index, token_len, fmt)
                index += token_len
            self.setCurrentBlockState(0)    
