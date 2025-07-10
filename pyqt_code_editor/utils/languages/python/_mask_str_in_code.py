import tokenize
import io
import re


def mask_str_in_code(code: str, mask_char: str = 'X') -> str:
    """Takes Python code and masks all characters that are part of a string
    by the mask_char.
    
    Examples:
    ---------

    In:

    print('test')
    
    Out:
    
    print('XXXX')
    
    In:
    
    print('A string with \'quotes\'')
    
    Out:
    
    print('XXXXXXXXXXXXXXXXXXXXXXXX')
    
    In:
    
    '''A triple quoted string
    across multiple lines
    '''
    
    Out:
    
    '''XXXXXXXXXXXXXXXXXXXXXX
    XXXXXXXXXXXXXXXXXXXXX
    '''
    """
    # First handle f-strings separately using regex
    # This regex matches f-strings with their content
    # Make sure 'f' is preceded by something that indicates start of a new token
    fstring_pattern = r'(?:^|[^a-zA-Z0-9_"\'])(f)(""".*?"""|\'\'\'.*?\'\'\'|".*?"|\'.*?\')'
    
    def mask_fstring(match):
        # Get the character before 'f' (if any)
        full_match = match.group(0)
        prefix_char = ''
        if not full_match.startswith('f'):
            prefix_char = full_match[0]
            
        prefix = match.group(1)  # 'f'
        full_string = match.group(2)
        quote = ''
        content = ''
        
        if full_string.startswith(('"""', "'''")):
            quote = full_string[:3]
            content = full_string[3:-3]
        else:
            quote = full_string[0]
            content = full_string[1:-1]
        
        # Mask everything in f-string content
        masked_content = mask_char * len(content)
        return prefix_char + prefix + quote + masked_content + quote
    
    # Apply f-string masking
    code = re.sub(fstring_pattern, mask_fstring, code, flags=re.DOTALL)
    
    # Now handle regular strings with tokenizer
    code_bytes = code.encode('utf-8')
    readline = io.BytesIO(code_bytes).readline
    
    masked_parts = []
    last_end = (1, 0)
    
    try:
        tokens = tokenize.tokenize(readline)
        
        for token in tokens:
            if token.type == tokenize.STRING:
                # Get the string content including quotes
                string_value = token.string
                # Skip if it looks like an f-string (already handled)
                if string_value.startswith(('f"', "f'", 'f"""', "f'''")):
                    # Add any code between last token and this one
                    start_line, start_col = token.start
                    end_line, end_col = last_end
                    
                    if start_line > end_line or (start_line == end_line and start_col > end_col):
                        lines = code.split('\n')
                        if end_line == start_line:
                            masked_parts.append(lines[end_line - 1][end_col:start_col])
                        else:
                            # Add remainder of last line
                            masked_parts.append(lines[end_line - 1][end_col:])
                            masked_parts.append('\n')
                            # Add intermediate lines
                            for line_num in range(end_line, start_line - 1):
                                masked_parts.append(lines[line_num])
                                masked_parts.append('\n')
                            # Add beginning of current line
                            masked_parts.append(lines[start_line - 1][:start_col])
                    
                    masked_parts.append(string_value)
                    last_end = token.end
                    continue
                
                # Determine quote style and content
                prefix = ''
                quote = ''
                end_quote = ''
                content = ''
                
                # Check for string prefix (r, b, u, etc. - but not f)
                i = 0
                while i < len(string_value) and string_value[i].lower() in 'rbux':
                    prefix += string_value[i]
                    i += 1
                
                remaining = string_value[i:]
                
                if remaining.startswith(('"""', "'''")):
                    quote = prefix + remaining[:3]
                    end_quote = remaining[-3:]
                    content = remaining[3:-3]
                elif remaining.startswith(('"', "'")):
                    quote = prefix + remaining[0]
                    end_quote = remaining[-1]
                    content = remaining[1:-1]
                
                # For regular strings, mask content while preserving newlines and leading spaces
                lines = content.split('\n')
                masked_lines = []
                
                for line in lines:
                    # Find leading whitespace
                    leading_space = ''
                    for char in line:
                        if char in (' ', '\t'):
                            leading_space += char
                        else:
                            break
                    
                    # Mask the rest of the line
                    rest_of_line = line[len(leading_space):]
                    masked_rest = mask_char * len(rest_of_line)
                    masked_lines.append(leading_space + masked_rest)
                
                masked_content = '\n'.join(masked_lines)
                
                masked_string = quote + masked_content + end_quote
                
                # Add any code between last token and this one
                start_line, start_col = token.start
                end_line, end_col = last_end
                
                if start_line > end_line or (start_line == end_line and start_col > end_col):
                    lines = code.split('\n')
                    if end_line == start_line:
                        masked_parts.append(lines[end_line - 1][end_col:start_col])
                    else:
                        # Add remainder of last line
                        masked_parts.append(lines[end_line - 1][end_col:])
                        masked_parts.append('\n')
                        # Add intermediate lines
                        for line_num in range(end_line, start_line - 1):
                            masked_parts.append(lines[line_num])
                            masked_parts.append('\n')
                        # Add beginning of current line
                        masked_parts.append(lines[start_line - 1][:start_col])
                
                masked_parts.append(masked_string)
                last_end = token.end
            
    except tokenize.TokenError:
        # Handle incomplete code
        pass
    
    # Add any remaining code
    lines = code.split('\n')
    end_line, end_col = last_end
    if end_line <= len(lines):
        masked_parts.append(lines[end_line - 1][end_col:])
        if end_line < len(lines):
            masked_parts.append('\n')
            masked_parts.extend('\n'.join(lines[end_line:]))
    
    return ''.join(masked_parts)