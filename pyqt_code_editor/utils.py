import os
from pygments.lexers import guess_lexer_for_filename
from pygments.util import ClassNotFound


def guess_language_from_path(filepath):
    """
    Detect programming language for a given file using Pygments.
    Returns a lowercase string, e.g. 'python', or falls back to 'text'.
    """
    if filepath is None:
        return 'text'
    try:
        # Read entire file as text (note: could be slow for very large files)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            contents = f.read()

        # Attempt to guess language
        lexer = guess_lexer_for_filename(filepath, contents)
        return lexer.name.lower()
    except (FileNotFoundError, ClassNotFound, UnicodeDecodeError):
        # If file doesn't exist or we can't guess the language,
        # we fall back to 'text'
        return 'text'


def shorten_paths(paths):
    """
    Given a list of file paths, return a list of shortened names that are unique,
    but only as long as necessary. Files sharing the same base name will get
    additional path components prepended from the right until they are unique.
    """
    
    # Split into lists of path components. We also note if the path is absolute.
    splitted = []
    for p in paths:
        # On some systems, you might want to use os.path.normpath first:
        # p = os.path.normpath(p)
        is_abs = p.startswith(os.path.sep)
        parts = p.strip(os.path.sep).split(os.path.sep)
        splitted.append((is_abs, parts))
    
    # Group by base name (last component)
    from collections import defaultdict
    base_map = defaultdict(list)
    for i, (is_abs, parts) in enumerate(splitted):
        base_map[parts[-1]].append(i)  # group by last component
    
    # For each group of files sharing the same base name, expand as necessary
    expansions = [1] * len(splitted)  # how many path parts (from the right) we are using
    
    def make_short_name(is_abs, parts, count):
        """
        Produce the short name using the last `count` components.
        If the original path was absolute and we use more than 1 component, we
        add a leading slash. (You can tweak this logic as desired.)
        """
        selected = parts[-count:]
        return "/".join(selected)

    
    for base_name, indices in base_map.items():
        if len(indices) == 1:
            # No conflict, no need to expand
            continue
        # We have multiple files with the same base name
        # so keep expanding path components until unique
        done = False
        while not done:
            # Build short names for all members
            used_names = {}
            collisions = False
            for idx in indices:
                is_abs, parts = splitted[idx]
                short = make_short_name(is_abs, parts, expansions[idx])
                if short in used_names:
                    collisions = True  # we have a collision
                used_names[short] = idx
            if collisions:
                # Increase expansions for all in this group
                for idx in indices:
                    expansions[idx] = min(expansions[idx] + 1, len(splitted[idx][1])) 
                # If expansions reach the entire path length, it can't expand further.
                # Next loop check might still find collisions if two paths are identical.
            else:
                done = True
    
    # Now build the final short names
    results = []
    for i, (is_abs, parts) in enumerate(splitted):
        count = expansions[i]
        short = make_short_name(is_abs, parts, count)
        results.append(short)
    
    return results

