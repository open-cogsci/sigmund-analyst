import re
import textwrap
from pyqt_code_editor import python_utils


def parse_autoindent_test_cases(test_cases: str) -> list[dict]:
    """
    Takes a string of test cases and turns these into a list of dict,
    where each dict is a test case:
    
        {
            "description": str,
            "code": str,
            "n_space": int
        }
    
    The 'description' is the line(s) preceding the code block.
    The 'code' is the block of lines (including the line marked with '>'),
    but with the '>' removed. The 'n_space' is how many leading spaces appear
    on the next line (the one containing '|').
    """

    # We'll split by triple-backtick code blocks and capture
    # the text in between for descriptions.
    parts = re.split(r"```(.*?)```", test_cases, flags=re.DOTALL)

    # The split results in a list where even indices (0, 2, 4, ...)
    # are text outside of code blocks, and odd indices (1, 3, 5, ...)
    # are the code blocks themselves.
    # For each code block at index i, the preceding text is at index i-1.

    results = []
    # We accumulate descriptions from the preceding text.
    for i in range(1, len(parts), 2):
        code_block = parts[i]
        preceding_text = parts[i - 1].rstrip()  # text in the preceding part
        # The last non-empty line of preceding_text is the description
        description_lines = preceding_text.split('\n')
        # Find the last line that isn't just whitespace
        desc_line = ""
        for line in reversed(description_lines):
            if line.strip():
                desc_line = line.strip()
                break
        lines = code_block.splitlines()
        code_lines = []
        n_space = 0
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if '>' in line:
                # Remove the '>' to reconstruct actual code
                line_without_arrow = line.replace('>', '')
                code_lines.append(line_without_arrow)

                # The next line should have '|' with possible indentation
                idx += 1
                if idx < len(lines):
                    next_line = lines[idx]
                    # Count leading spaces
                    leading_spaces = len(next_line) - len(next_line.lstrip(' '))
                    n_space = leading_spaces
                break
            else:
                code_lines.append(line)
            idx += 1

        code_str = "\n".join(code_lines)

        results.append({
            "description": desc_line,
            "code": code_str,
            "n_space": n_space
        })

    return results
   
    
def test_utils(assert_pass=True):
    for fnc in [
        python_utils._indent_inside_unclosed_call_def_or_class,
        python_utils._indent_after_block_opener,
        python_utils._indent_inside_uncloded_list_tuple_set_or_dict,
        python_utils._indent_after_list_tuple_set_or_dict,
        python_utils.python_auto_indent,
    ]:
        markdown_test_cases = textwrap.dedent(fnc.__doc__)
        test_cases = parse_autoindent_test_cases(markdown_test_cases)
        total = 0
        passed = 0
        for test_case in test_cases:
            print('\n\n# ' + test_case['description'])
            print('\nExpecting:')
            print(test_case['code'] + '>\n' + '.' * test_case['n_space'] + '|')
            print('\nReceived:')
            indent = python_utils.python_auto_indent(test_case['code'])
            print(test_case['code'] + '>\n' + '.' * indent + '|')
            total += 1
            if assert_pass:
                assert test_case['n_space'] == indent
            if test_case['n_space'] == indent:
                print('\nPASS')
                passed += 1
            else:
                print('\nFAIL')
                assert False
        print(f'\n\n{passed}/{total} passed')
    
    
if __name__ == "__main__":
    test_utils(assert_pass=False)
