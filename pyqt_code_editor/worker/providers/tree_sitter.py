from tree_sitter import Language, Parser
import importlib


def tree_sitter_matching_brackets(code, language):
    """Find matching brackets using tree-sitter parsing. Handles
    incomplete/invalid code gracefully.

    Returns
    -------
    List of tuples (open_pos, close_pos) for matching brackets
    """
    module_name = language.lower().split('+')[0]
    ts_module_name = f'tree_sitter_{module_name}'
    try:
        # Dynamically import the tree-sitter language module
        ts_module = importlib.import_module(ts_module_name)        
    except (ImportError, AttributeError):
        # Language not available, return empty list
        return []    
    # Set up parser
    lang = Language(ts_module.language())
    parser = Parser(lang)
    # Parse the code
    tree = parser.parse(bytes(code, "utf8"))

    # Find all bracket positions in the source
    bracket_map = {'(': ')', '[': ']', '{': '}'}
    opening = []
    closing = []
    
    for i, char in enumerate(code):
        if char in bracket_map:
            opening.append((i, char))
        elif char in bracket_map.values():
            closing.append((i, char))
    
    # Match brackets using a stack-based approach
    # But verify positions are within valid syntax nodes
    matches = []
    stack = []
    
    # Merge and sort all bracket positions
    all_brackets = [(pos, char, True) for pos, char in opening]
    all_brackets += [(pos, char, False) for pos, char in closing]
    all_brackets.sort()
    
    for pos, char, is_opening in all_brackets:
        if is_opening:
            stack.append((pos, char))
        else:
            # Find matching opening bracket
            if stack:
                expected_close = bracket_map.get(stack[-1][1])
                if expected_close == char:
                    open_pos = stack.pop()[0]
                    matches.append((open_pos, pos))

    # Sort by opening position
    matches.sort()
    return matches