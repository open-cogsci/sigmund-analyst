import re
from . import settings
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


def get_leading_spaces(line: str) -> int:
    """
    Return the number of leading spaces in line.
    """
    return len(line) - len(line.lstrip(' '))


def parse_brackets(code: str):
    """
    Parse all lines of code, ignoring quoted strings in a simple way,
    and return:
        bracket_stack: A list of unclosed brackets in order of appearance,
                       each as (bracket_char, line_index, col_index).
        bracket_closings: A dict mapping close_line_idx -> (open_line_idx, open_line_indent, open_bracket).
    """
    open_to_close = {'(': ')', '[': ']', '{': '}'}
    close_to_open = {')': '(', ']': '[', '}': '{'}
    
    # A naive bracket parser that ignores strings by removing them first
    # (this is simplistic; real logic may need to handle triple quotes, etc.)
    def remove_strings(line: str) -> str:
        return re.sub(r'(".*?"|\'.*?\')', '', line)
    
    lines = code.split("\n")
    bracket_stack = []
    bracket_closings = {}
    
    for i, raw_line in enumerate(lines):
        # remove quoted strings
        stripped_line = remove_strings(raw_line)
        
        j = 0
        while j < len(stripped_line):
            ch = stripped_line[j]
            if ch in open_to_close:
                bracket_stack.append((ch, i, j))
            elif ch in close_to_open:
                # If there's something on the stack and it matches, pop it
                if bracket_stack and bracket_stack[-1][0] == close_to_open[ch]:
                    open_bracket_char, open_line_idx, open_col_idx = bracket_stack.pop()
                    # record the closing bracket
                    bracket_closings[i] = (open_line_idx, get_leading_spaces(lines[open_line_idx]), open_bracket_char)
            j += 1
    
    return bracket_stack, bracket_closings
    

def _indent_inside_unclosed_call_def_or_class(code: str) -> int:
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
    """
    lines = code.splitlines()
    if not lines:
        return 0

    # Count unclosed parentheses and track last open parenthesis position
    open_count = code.count('(')
    close_count = code.count(')')
    if open_count <= close_count:
        return 0

    bracket_stack, _ = parse_brackets(code)

    # Find the last open '(' in bracket_stack
    last_open_paren = None
    for (b_char, line_idx, col_idx) in reversed(bracket_stack):
        if b_char == '(':
            last_open_paren = (line_idx, col_idx)
            break
    
    if not last_open_paren:
        return 0

    line_idx, col_idx = last_open_paren
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


def _indent_after_block_opener(code: str) -> int:
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
    BLOCK_KEYWORDS = (
        "def", "class", "if", "elif", "else", "while", 
        "for", "with", "try", "except", "finally"
    )
    
    def is_block_opener(line: str) -> bool:
        stripped = line.lstrip()
        lower_stripped = stripped.lower()
        for kw in BLOCK_KEYWORDS:
            if lower_stripped.startswith(kw) and (
                len(stripped) == len(kw)
                or stripped[len(kw)] in (' ', '(', ':')
            ):
                return True
        return False
    
    lines = code.splitlines()
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
        if is_block_opener(lines[i]):
            block_opener_idx = i
            break
    
    block_opener_indent = get_leading_spaces(lines[block_opener_idx])
    return block_opener_indent + settings.tab_width
    
    
def _indent_inside_uncloded_list_tuple_set_or_dict(code: str) -> int:
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

    bracket_stack, _ = parse_brackets(code)

    # Find last unclosed bracket
    last_open = None
    open_brackets = {'(': ')', '[': ']', '{': '}'}
    for b_char, l_idx, c_idx in reversed(bracket_stack):
        if b_char in open_brackets:
            last_open = (b_char, l_idx, c_idx)
            break

    if not last_open:
        # no unclosed bracket
        return 0

    bracket_char, bracket_line_idx, bracket_col_idx = last_open
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


def _indent_after_list_tuple_set_or_dict(code: str) -> int:
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
    """
    lines = code.split('\n')
    if not lines:
        return 0
    
    bracket_stack, bracket_closings = parse_brackets(code)
    last_line_idx = len(lines) - 1
    last_line = lines[last_line_idx]
    last_line_indent = get_leading_spaces(last_line)

    if last_line and last_line[-1] in (')', ']', '}'):
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
    """
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
        return _indent_after_block_opener(code)

    # 2. unmatched '(' => function call/def or tuple
    open_paren_count = code.count("(")
    close_paren_count = code.count(")")
    if open_paren_count > close_paren_count:
        last_paren_idx = code.rfind("(")
        if last_paren_idx > 0:
            preceding_idx = last_paren_idx - 1
            while preceding_idx >= 0 and code[preceding_idx].isspace():
                preceding_idx -= 1
            if preceding_idx >= 0:
                preceding_char = code[preceding_idx]
                # If preceding char is alnum or _, treat as function call/def
                if preceding_char.isalnum() or preceding_char == "_":
                    logging.info("indent as unclosed call/def")
                    return _indent_inside_unclosed_call_def_or_class(code)
                else:
                    logging.info("indent as unclosed iterable")
                    return _indent_inside_uncloded_list_tuple_set_or_dict(code)
            else:
                logging.info("indent as unclosed iterable")
                # Nothing precedes '(' => treat as tuple
                return _indent_inside_uncloded_list_tuple_set_or_dict(code)
        else:
            # '(' is at index 0 or not found
            logging.info("indent as unclosed iterable")
            return _indent_inside_uncloded_list_tuple_set_or_dict(code)

    # 3. unmatched '[' or '{'
    open_square_count = code.count("[")
    close_square_count = code.count("]")
    open_brace_count = code.count("{")
    close_brace_count = code.count("}")
    if (open_square_count > close_square_count) or (open_brace_count > close_brace_count):
        logging.info("indent as unclosed iterable")
        return _indent_inside_uncloded_list_tuple_set_or_dict(code)

    # 4. just closed a bracket => after bracket
    if last_line.endswith(("]", "}", ")")):
        logging.info('indent as after iterable')
        return _indent_after_list_tuple_set_or_dict(code)

    # 5. fallback => preserve current line indent
    current_line_full = lines[-1]
    leading_spaces = get_leading_spaces(current_line_full)
    return leading_spaces
