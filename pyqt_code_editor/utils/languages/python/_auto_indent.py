from .... import settings
from ._mask_str_in_code import mask_str_in_code
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

BLOCK_KEYWORDS = (
    "def", "class", "if", "elif", "else", "while", 
    "for", "with", "try", "except", "finally"
)
OPEN_TO_CLOSE = {'(': ')', '[': ']', '{': '}'}
CLOSE_TO_OPEN = {')': '(', ']': '[', '}': '{'}    


def get_leading_spaces(line: str) -> int:
    """
    Return the number of leading spaces in line.
    """
    return len(line) - len(line.lstrip(' '))

    
def _is_block_opener(line: str) -> bool:
    stripped = line.lstrip()
    lower_stripped = stripped.lower()
    for kw in BLOCK_KEYWORDS:
        if lower_stripped.startswith(kw) and (
            len(stripped) == len(kw)
            or stripped[len(kw)] in (' ', '(', ':')
        ):
            return True
    return False


def parse_brackets(code: str) -> tuple[list[tuple[str, int, int]], dict]:
    """
    Parse all lines of code, ignoring quoted strings in a simple way,
    and return:
        bracket_stack: A list of unclosed brackets in order of appearance,
                       each as (bracket_char, line_index, col_index).
        bracket_closings: A dict mapping close_line_idx -> (open_line_idx, open_line_indent, open_bracket).
    """

    lines = code.split("\n")
    bracket_stack = []
    bracket_closings = {}
    
    for i, line in enumerate(lines):        
        j = 0
        while j < len(line):
            ch = line[j]
            if ch in OPEN_TO_CLOSE:
                bracket_stack.append((ch, i, j))
            elif ch in CLOSE_TO_OPEN:
                # If there's something on the stack and it matches, pop it
                if bracket_stack and bracket_stack[-1][0] == CLOSE_TO_OPEN[ch]:
                    open_bracket_char, open_line_idx, open_col_idx = bracket_stack.pop()
                    # record the closing bracket
                    bracket_closings[i] = (open_line_idx, get_leading_spaces(lines[open_line_idx]), open_bracket_char)
            j += 1
    
    return bracket_stack, bracket_closings
    
    
def _get_unclosed_open_idx(code : str, open_char : str,
                           close_char : str) -> int | None:
    """Returns the index of the last unclosed unopening character, such as an
    opening parenthesis, or None if no unclosed opening character was found.
    """
    # We only consider code from the end of the last code comment. This is a
    # cheap way to avoid the auto indenter from being confused by parentheses
    # in comments.
    last_comment = code.rfind('#')
    if last_comment >= 0:
        last_comment_end = code[last_comment:].find('\n')
        if last_comment_end >= 0:
            last_comment += last_comment_end
    search_start = max(0, last_comment)
    if search_start:
        code = code[search_start:]
    n_open_required = 1    
    while n_open_required:
        close_idx = code.rfind(close_char)
        open_idx = code.rfind(open_char)
        if close_idx < 0 and open_idx < 0:
            break
        if open_idx > close_idx:
            n_open_required -= 1
            code = code[:open_idx]
        else:
            n_open_required += 1
            code = code[:close_idx]
    if open_idx < 0:
        return 0
    return open_idx + search_start


def _line_col_from_idx(full_text, char_index):
    """
    Return the 0-based (line, column) pair in `full_text` for the given `char_index`.
    If char_index is out of range, this function raises an IndexError.
    """
    if not (0 <= char_index < len(full_text)):
        raise IndexError("char_index out of range.")

    line = 0
    column = 0
    idx = 0

    for ch in full_text:
        if idx == char_index:
            return (line, column)
        if ch == '\n':
            line += 1
            column = 0
        else:
            column += 1
        idx += 1

    # If char_index matches len(full_text)-1, return the final position:
    return (line, column)    
    

def _indent_inside_unclosed_call_def_or_class(code: str, lines: list,
                                              char_idx : int) -> int:
    """
    Return after opening parenthesis as part of function call should trigger indent
    
    ```
    function(>
        |
    ```    
    
    Return after parenthesis after function definition should trigger indent
    
    ```
    def test(>
        |
    ```
    
    Return after parenthesis after class definition should trigger indent
    
    ```
    class Test(>
        |
    ```
    
    Return after opening parenthesis and one or more arguments as part of function call should trigger matching indent to first argument
    
    ```
    function(arg1,>
             |
    ```
             
    Return after opening parenthesis and one or more arguments as part of function call should trigger matching indent to first argument, also when the argument contains default values with strings.
    
    ```
    function("arg1", arg2='default', arg3=\"\"\"test\"\"\",>
             |
    ```
        
    Return after parenthesis and one or more arguments after function definition should trigger matching indent to first argument
    
    ```
    def test(arg1,>
             |
    ```
    
    Return after parenthesis and one or more arguments after class definition should trigger matching indent to first argument
    
    ```
    class Test(object,>
               |
    ```

    Return after opening parenthesis and one or more arguments on the next line as part of function call should trigger matching indent to first argument
    
    ```
    function(
        arg1,>
        |
    ```   
        
    Return after parenthesis and one or more arguments on the next line after function definition should trigger matching indent to first argument
    
    ```
    def test(
        arg1,>
        |
    ```
    
    Return after parenthesis and one or more arguments after class definition should trigger matching indent to first argument
    
    ```
    class Test(
        object,>
        |
    ```
    
    Return after opening parenthesis should also work in nested situations
    
    ```
    class Test:
        def test(>
            |
    ```
                 
    Return after opening parenthesis with arguments should also work in nested situations
    
    ```
    class Test:
        def test(arg1,>
                 |
    ```
                 
    Return after opening parenthesis with arguments should also work in nested situations
    
    ```
    class Test:
        def test(
            arg1,>
            |
    ```
            
    Return after opening parenthesis should also work with irrelevant parentheses
    
    ```
    # 1) a list item
    class Test:
        def test(>
            |
    ```
                       
    Return after opening parenthesis should also work with irrelevant parentheses
    
    ```
    # (1 a list item
    class Test:
        def test(>
            |
    ```            
    """
    if not lines:
        return 0    
    line_idx, col_idx = _line_col_from_idx(code, char_idx)
    # Get the line where the last unclosed parenthesis is
    open_line = lines[line_idx]
    # Collect text after '(' in that line
    text_after_paren = open_line[col_idx + 1:].rstrip()
    # If there's no text after '(' on the same line, just indent by tab
    if not text_after_paren:
        # Get indentation of open_line
        open_line_indent = len(open_line) - len(open_line.lstrip())
        return open_line_indent + settings.tab_width
    # Otherwise, align with the first non-whitespace character after '('
    prefix = open_line[: col_idx + 1]
    after_paren_offset = 0
    for char in open_line[col_idx + 1:]:
        if char.isspace():
            after_paren_offset += 1
        else:
            break

    return len(prefix) + after_paren_offset


def _indent_after_block_opener(code: str, lines: list) -> int:
    """
    Return after function definition should trigger indent
    
    ```
    def test():>
        |
    ```
    
    Return after class definition should trigger indent
    
    ```
    class Test:>
        |
    ```
          
    Return after class definition with inheritance should trigger indent
    
    ```
    class Test(object):>
        |
    ```
    
    Return after colon after function definition should dedent to function level, regardless of the indentation of the current line
    
    ```
    def test(arg1,
             arg2):>
        |
    ```
    
    Return after colon after class definition should dedent to class level, regardless of the indentation of the current line
    
    ```
    class Test(object1,
               object2):>
        |
    ```
                                                                       
    Return after function definition should also work with irrelevant parentheses
    
    ```
    # 1) a list item
    class Test:
        def test():>
            |
    ```
                       
    Return after function definition should also work with irrelevant parentheses
    
    ```
    # (1 a list item
    class Test:
        def test():>
            |                                                                       
    
    Return after colon after while should trigger indent:
        
    ```
    while True:>
        |
    ```
    
    Return after colon after for should trigger indent:
        
    ```
    for i in range(10):>
        |
    ```
    
    Return after if should trigger indent:
        
    ```
    if x == y:>
        |
    ```
    
    Return after else should trigger indent:
        
    ```
    else:>
        |
    ```
    
    Return after elif should trigger indent:
        
    ```
    elif x == y:>
        |
    ```
    
    Return after colon after with should trigger indent:
        
    ```
    with context:>
        |
    ```
    
    Return after colon after with ... as should trigger indent:
        
    ```
    with context as obj:>
        |
    ```
    
    Return after try should trigger indent:
        
    ```
    try:>
        |
    ```
    
    Return after except should trigger indent:
        
    ```
    except:>
        |
    ```
    
    Return after except ... some exception class should trigger indent:
        
    ```
    except Exception:>
        |
    ```
    Return after except ... as should trigger indent:
        
    ```
    except Exception as e:>
        |
    ```
    
    Return after finally should trigger indent:
        
    ```
    finally:>
        |
    ```
               
    Indent after function definition should also work in nested situations:
        
    ```
    class Test:
        def test():>
            |
    ```
               
    Indent after if should also work in nested situations:
        
    ```
    def test():
        if x == y:>
            |
    ```
    """    
    if not lines:
        return 0
    
    last_line = lines[-1]
    trimmed_line = last_line.rstrip()
    if not trimmed_line.endswith(':'):
        # just return current line's indentation
        return get_leading_spaces(last_line)
    
    # If it DOES end with a colon, we see if we can locate the block opener line
    block_opener_idx = len(lines) - 1
    for i in range(len(lines) - 1, -1, -1):
        if _is_block_opener(lines[i]):
            block_opener_idx = i
            break
    
    block_opener_indent = get_leading_spaces(lines[block_opener_idx])
    return block_opener_indent + settings.tab_width
    
    
def _indent_inside_uncloded_list_tuple_set_or_dict(code: str, char_idx: int) -> int:
    """
    Return after opening of list should trigger matching indent to first element
    
    ```
    l = [>
         |
    ```
    
    Return after opening of tuple should trigger matching indent to first element
    
    ```
    t = (>
         |
    ```
    
    Return after opening of set should trigger matching indent to first element
    
    ```
    s = {>
         |
    ```
    
    Return after opening of dict should trigger matching indent to first element
    
    ```
    d = {>
         |
    ```
    
    Return after opening of list with one or more elements should trigger matching indent to first element
    
    ```
    l = [item1,>
         |
    ```
         
    Return after opening of list with one or more elements should trigger matching indent to first element, also when the element is a string
    
    ```
    l = ['item1',>
         |
    ```
    
    Return after opening of tuple with one or more elements should trigger matching indent to first element
    
    ```
    t = (item1,>
         |
    ```
    
    Return after opening of set with one or more elements should trigger matching indent to first element
    
    ```
    s = {item1,>
         |
    ```
    
    Return after opening of dict with one or more elements should trigger matching indent to first element
    
    ```
    d = {key1:val1,>
         |
    ```
    
    Return after opening of list with one or more elements on the next line should trigger matching indent to first element
    
    ```
    l = [
        item1,>
        |
    ```
    
    Return after opening of tuple with one or more elements on the next line should trigger matching indent to first element
    
    ```
    t = (
        item1,>
        |
    ```
    
    Return after opening of set with one or more elements on the next line should trigger matching indent to first element
    
    ```
    s = {
        item1,>
        |
    ```
    
    Return after opening of dict with one or more elements on the next line should trigger matching indent to first element
    
    ```
    d = {
        key1:val1,>
        |
    ```
        
    Return after opening of list should also work in nested situations:
    
    ```
    def test():
        l = [>
             |
    ```
    
    Return after opening of list with one or more elements should also work in nested situations:
    
    ```
    def test():
        l = [item1,>
             |
    ```
    
    Return after opening of list with one or more elements on the next line should also work in nested situations:
    
    ```
    def test():
        l = [
            item1,>
            |
    ```        
    """
    lines = code.split('\n')
    if not lines:
        return 0
    bracket_line_idx, bracket_col_idx = _line_col_from_idx(code, char_idx)
    # Get the line where the last unclosed parenthesis is
    bracket_line = lines[bracket_line_idx]            
    bracket_line_indent = get_leading_spaces(bracket_line)

    # Check text after bracket on same line
    post_bracket_text_idx = None
    for i in range(bracket_col_idx + 1, len(bracket_line)):
        if bracket_line[i] not in (' ', '\t'):
            post_bracket_text_idx = i
            break

    if post_bracket_text_idx is not None:
        # Align to the first non-whitespace character after bracket
        return post_bracket_text_idx
    else:
        # No text after bracket on the same line
        # find next non-empty line
        next_non_empty_line_idx = None
        for i in range(bracket_line_idx + 1, len(lines)):
            if lines[i].strip():
                next_non_empty_line_idx = i
                break

        if next_non_empty_line_idx is None:
            # no subsequent non-empty lines
            return bracket_col_idx + 1
        else:
            # align to the first non-whitespace character of the next line
            next_line = lines[next_non_empty_line_idx]
            for i, ch in enumerate(next_line):
                if ch not in (' ', '\t'):
                    return i
            return bracket_col_idx + 1


def _indent_after_list_tuple_set_or_dict(code: str, bracket_stack, bracket_closings) -> int:
    """
    Return after closing of a single-line list should not change indentation.
    
    ```
    l = [element1, element2]>
    |
    ```
    
    Return after closing of a single-line tuple should not change indentation.
    
    ```
    t = [element1, element2]>
    |
    ```
    
    Return after closing of a single-line set should not change indentation.
    
    ```
    s = {element1, element2}>
    |
    ```
    
    Return after closing of a single-line list should not change indentation.
    
    ```
    d = {key1: val1, key2: val2}>
    |
    ```
    
    Return after closing of list should trigger dedent to scope level, regardless of the indentation of the current line
    
    ```
    l = [element1,
         element2]>
    |
    ```
    
    Return after closing of tuple should trigger dedent to scope level, regardless of the indentation of the current line
    
    ```
    t = (element1,
         element2)>
    |
    ```
    
    Return after closing of set should trigger dedent to scope level, regardless of the indentation of the current line
    
    ```
    s = {element1,
         element2}>
    |
    ```
    
    Return after closing of dict should trigger dedent to scope level, regardless of the indentation of the current line
    
    ```
    d = {key1: val1,
         key2: val2}>
    |
    ```
            
    Return after closing of dict should als work with trailing spaces
    
    ```
    d = {key1: val1,
         key2: val2} >
    |
    ```
    """
    lines = code.split('\n')
    if not lines:
        return 0
    
    last_line_idx = len(lines) - 1
    last_line = lines[last_line_idx]
    last_line_indent = get_leading_spaces(last_line)
    if last_line and last_line.rstrip()[-1] in (')', ']', '}'):
        # We closed a bracket
        if last_line_idx in bracket_closings:
            open_line_idx, open_line_indent, open_bracket = bracket_closings[last_line_idx]
            if open_line_idx == last_line_idx:
                # single-line bracket => no change
                return last_line_indent
            else:
                # multi-line => dedent to open bracket line's indent
                return open_line_indent
        else:
            # bracket not found or mismatched => no change
            return last_line_indent
    else:
        # no bracket close => no change
        return last_line_indent
        
            
def python_auto_indent(code: str) -> int:
    """
    As fallback, should preserve indentation of previous line.
    
    ```
    def test():
        pass>
        |
    ```
    
    As fallback, should preserve indentation of previous line.
    
    ```
    def test():
        pass
    >
    |
    ```
             
    Should dedent after return
    
    ```
    def test():
        return>
    |
    ```
    
    Should not be affected by irrelevant whitespace

    ```
    # 1) list item
    x = 1>
    |
    ```
             
    Should not be affected by irrelevant whitespace

    ```
    # (1 list item
    x = 1>
    |
    ```
    """
    code = mask_str_in_code(code)
    lines = code.splitlines()
    # If code ends with a newline => cursor is on a fresh line
    if code.endswith('\n'):
        lines.append('')
    if not lines:
        return 0
    last_line = lines[-1].rstrip()

    # 1. ends with colon => block opener
    if last_line.endswith(":"):
        logging.info('indent after block opener')
        return _indent_after_block_opener(code, lines)
            
    # 2. unmatched '(' => function call/def or tuple
    last_paren_idx_tuple = _get_unclosed_open_idx(code, '(', ')')
    if last_paren_idx_tuple:
        preceding_idx = last_paren_idx_tuple - 1
        while preceding_idx >= 0 and code[preceding_idx].isspace():
            preceding_idx -= 1
        if preceding_idx >= 0:
            preceding_char = code[preceding_idx]
            # If preceding char is alnum or _, treat as function call/def
            if preceding_char.isalnum() or preceding_char == "_":
                logging.info("indent as unclosed call/def")
                return _indent_inside_unclosed_call_def_or_class(
                    code, lines, last_paren_idx_tuple)
            else:
                logging.info("indent as unclosed tuple")
                return _indent_inside_uncloded_list_tuple_set_or_dict(
                    code, last_paren_idx_tuple)

    # 3. unmatched '[' or '{'
    last_paren_idx_list = _get_unclosed_open_idx(code, '[', ']')
    last_paren_idx_dict = _get_unclosed_open_idx(code, '{', '}')
    char_idx = max(last_paren_idx_list, last_paren_idx_dict)
    if char_idx:
        logging.info("indent as unclosed list, dict, or set")
        return _indent_inside_uncloded_list_tuple_set_or_dict(code, char_idx)

    # 4. just closed a bracket => after bracket
    bracket_stack, bracket_closings = parse_brackets(code)
    if last_line.endswith(("]", "}", ")")):
        logging.info('indent as after iterable')
        return _indent_after_list_tuple_set_or_dict(
            code, bracket_stack, bracket_closings)

    # 5. Check if the current line is a dedent keyword
    current_line_full = lines[-1]
    current_line_strip = current_line_full.strip()
    leading_spaces = get_leading_spaces(current_line_full)
    if current_line_strip  in ('return', 'break', 'continue'):
        return max(0, leading_spaces - settings.tab_width)
        
    # 6. Check if the current line starts with def or class. If so then we need 
    # to indent. This is a fallback mechanism to catch situations in which this
    # was not properly caught by the above logic.    
    if current_line_strip.startswith('def') or current_line_strip .startswith('class'):
        logging.info('fallback indent as def or class')
        return leading_spaces + settings.tab_width
                     
    # 7. fallback => preserve current line indent
    logging.info('indent fallback to current line')
    return leading_spaces
