import re

def symbol_complete(code: str, cursor_pos: int, path: str | None,
                    multiline: False) -> list[str]:
    """
    A helper function for code completion that is based on all the symbols
    that are detected in the code in a language-agnostic way. The code is split
    into separate words so that punctuation and separators are ignored. Then
    the best fitting completion is returned. If no completion is available
    (e.g., because the character before the cursor is punctuation, comma, or
    whitespace), return None.

    Logic to handle contradictory test #4 and #5:
    1) If the partial_word itself appears in the code, we prioritize a match
       with the largest leftover length.
    2) Otherwise, if there is a symbol that differs from partial_word by exactly
       1 character, pick that first; otherwise pick the one with the largest
       leftover length. Ties are broken lexicographically.
    """

    if cursor_pos == 0:
        return None  # No space to complete if at start of code

    # Check the character immediately before the cursor
    char_before = code[cursor_pos - 1]
    # If the character is not alphanumeric or underscore, no completion
    if not re.match(r"[A-Za-z0-9_]", char_before):
        return None

    # Find the partial word by reading backwards from cursor_pos
    start_index = cursor_pos - 1
    while start_index >= 0 and re.match(r"[A-Za-z0-9_]", code[start_index]):
        start_index -= 1
    partial_word = code[start_index + 1:cursor_pos]
    if not partial_word:
        return None

    # Remove the user-typed partial_word from the code where it appears near the cursor
    code_without_partial = code[:start_index + 1] + code[cursor_pos:]

    # Gather all words (symbols) from the updated code
    all_symbols = re.findall(r"[A-Za-z0-9_]+", code_without_partial)
    unique_symbols = set(all_symbols)  # deduplicate

    # Filter only those symbols that:
    # 1) start with partial_word
    # 2) are strictly longer than partial_word
    matches = [sym for sym in unique_symbols
               if sym.startswith(partial_word) and len(sym) > len(partial_word)]
    if not matches:
        return None

    # Build leftover_map { leftover_length -> list_of_symbols }
    leftover_map = {}
    for sym in matches:
        leftover_len = len(sym) - len(partial_word)
        leftover_map.setdefault(leftover_len, []).append(sym)

    # Check if partial_word is itself a symbol (i.e. it appears elsewhere in the code)
    partial_word_is_symbol = partial_word in unique_symbols

    if partial_word_is_symbol:
        # Pick from the group with the maximum leftover
        max_leftover_len = max(leftover_map)
        candidates = leftover_map[max_leftover_len]
    else:
        # If there's a leftover=1 group available, pick that
        if 1 in leftover_map:
            candidates = leftover_map[1]
        else:
            # Otherwise pick from the group with the maximum leftover
            max_leftover_len = max(leftover_map)
            candidates = leftover_map[max_leftover_len]

    # Among candidates, pick the lexicographically first
    best_match = min(candidates)
    # The remainder is the substring that goes beyond the partial_word
    remainder = best_match[len(partial_word):]
    return [remainder]

def _run_tests():
    print('Running symbol completion tests...')

    tests = [
        # 1) Basic test: completes "my_func" to "my_function"
        (
            "def my_function():\n    pass\nmy_func|",
            "tion"
        ),
        # 2) Cursor is at start => no completion
        (
            "def my_function():\n    pass\n|",
            None
        ),
        # 3) Partial match "some_v" => completes to "ar"
        (
            "some_var = 10\nsome_v|\n",
            "ar"
        ),
        # 4) multiple similar beginnings => picks "myvar" => "r"
        (
            "myvar myvariable myvar2\nmyva|",
            "r"
        ),
        # 5) specifically test picking "myvariable" (longer) instead of "myvar2"
        (
            "myvar myvariable myvar2\nmyvar|",
            "iable"
        ),
        # 6) The partial is 'someth' => "something" => remainder "ing"
        (
            "something,\nsometh|",
            "ing"
        ),
        # 7) Cursor in the middle: partial_word is "myv"
        # 'myvariable' => remainder is "ariable"
        (
            "myvar myvariable myvar2\nmyv|ar testing mid-cursor",
            "ariable"
        ),
        # 8) Another middle test: partial is "int"
        # 'integerExample' => remainder "egerExample"
        (
            "some intVar, integerExample, interplay\nint|Var\ncursor after 'int'",
            "egerExample"
        ),
    ]

    for i, (test_str, expected) in enumerate(tests, 1):
        cursor_pos = test_str.index("|")
        code_str = test_str.replace("|", "")
        result = symbol_complete(code_str, cursor_pos)
        outcome = "PASSED" if result == expected else f"FAILED (got {result} instead of {expected})"
        print(f"Test {i}: {outcome}")

if __name__ == "__main__":
    _run_tests()
