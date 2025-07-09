import re


def extract_cells_from_code(code: str) -> list:
    """Extracts cells from code. The return value is a 
    list of cells, where each cell is a dict like so:

    {
        'description': str | None,
        'start_pos': int,
        'end_pos': int,
        'code': str
    }

    A description only applies to cells that have been defined with
    triple-quoted strings. Otherwise it is None.
    
    Cells can be defined by:
    - # %%
    - #%%
    - # In[]:
    - Triple-quoted strings
    """
    # Store all detected cells
    cells = []
    
    # Define regex patterns for cell markers
    marker_pattern = re.compile(r'^(# %%|#%%|# In\[\]:?).*?$', re.MULTILINE)
    triple_quotes_pattern = re.compile(
        r'(?m)^(""".*?"""|\'\'\'.*?\'\'\')',
        re.DOTALL
    )
    
    # Find all marker-based cells
    marker_matches = list(marker_pattern.finditer(code))
    
    # Find all triple-quoted docstrings that are at the top level
    # (we'll filter out non-top-level ones later)
    docstring_matches = list(triple_quotes_pattern.finditer(code))
    
    # Combine all match types and sort by position
    all_markers = []
    
    # Add marker matches
    for match in marker_matches:
        start_pos = match.start()
        all_markers.append({
            'type': 'marker',
            'match': match,
            'start_pos': start_pos
        })
    
    # Add docstring matches
    for match in docstring_matches:
        start_pos = match.start()
        # Only include if not inside string/comment (simplified check)
        # We'll do more thorough validation later
        all_markers.append({
            'type': 'docstring',
            'match': match,
            'start_pos': start_pos
        })
    
    # Sort all markers by position
    all_markers.sort(key=lambda x: x['start_pos'])
    
    # Process each marker to create cells
    for i, marker in enumerate(all_markers):
        match = marker['match']
        start_pos = marker['start_pos']
        
        # Determine where this cell ends (next marker or end of file)
        if i < len(all_markers) - 1:
            end_pos = all_markers[i + 1]['start_pos']
        else:
            end_pos = len(code)
        
        # Check if this docstring is actually a top-level triple-quoted string
        # and not part of a function definition, string literal, etc.
        if marker['type'] == 'docstring':
            # Skip if not a top-level docstring (simplified check)
            # This is a simplification; a more robust solution would check code structure
            line_start = code.rfind('\n', 0, start_pos) + 1
            if line_start < start_pos:
                indent = code[line_start:start_pos].strip()
                if indent:  # If there's text before the docstring on the same line, skip it
                    continue
            
            # Extract description from the docstring
            docstring_content = match.group(0)[3:-3].strip()
            
            # Extract code content (from end of docstring to end of cell)
            docstring_end = match.end()
            cell_code = code[docstring_end:end_pos].strip()
            
            cells.append({
                'description': docstring_content,
                'start_pos': start_pos,
                'end_pos': end_pos,
                'code': cell_code
            })
            
        else:  # Marker-based cell
            # Extract code content (from end of marker line to end of cell)
            marker_line_end = code.find('\n', start_pos)
            if marker_line_end == -1:  # If no newline is found
                marker_line_end = len(code)
            
            cell_code = code[marker_line_end + 1:end_pos].strip()
            
            cells.append({
                'description': None,
                'start_pos': start_pos,
                'end_pos': end_pos,
                'code': cell_code
            })
    
    # Handle the case where the file starts with code before any marker
    if all_markers and all_markers[0]['start_pos'] > 0:
        first_code = code[:all_markers[0]['start_pos']].strip()
        if first_code:
            cells.insert(0, {
                'description': None,
                'start_pos': 0,
                'end_pos': all_markers[0]['start_pos'],
                'code': first_code
            })
    
    # Handle the case where there are no markers at all
    if not cells and code.strip():
        cells.append({
            'description': None,
            'start_pos': 0,
            'end_pos': len(code),
            'code': code.strip()
        })
    
    return cells
