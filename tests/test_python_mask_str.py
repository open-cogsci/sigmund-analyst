from pyqt_code_editor.utils.languages.python import mask_str_in_code


def test_simple_single_quote():
    code = "print('test')"
    result = mask_str_in_code(code)
    assert result == "print('XXXX')"

def test_simple_double_quote():
    code = 'print("test")'
    result = mask_str_in_code(code)
    assert result == 'print("XXXX")'

def test_escaped_quotes():
    code = "print('A string with \\'quotes\\'')"
    result = mask_str_in_code(code)
    expected = "print('XXXXXXXXXXXXXXXXXXXXXXXX')"
    assert result == expected

def test_triple_quoted_string():
    code = '''"""A triple quoted string
across multiple lines
"""'''
    result = mask_str_in_code(code)
    expected = '''"""XXXXXXXXXXXXXXXXXXXXXX
XXXXXXXXXXXXXXXXXXXXX
"""'''
    assert result == expected

def test_mixed_strings():
    code = '''print("Hello") + print('World')'''
    result = mask_str_in_code(code)
    assert result == '''print("XXXXX") + print('XXXXX')'''

def test_f_string():
    code = '''name = "John"
print(f"Hello {name}!")'''
    result = mask_str_in_code(code)
    expected = '''name = "XXXX"
print(f"XXXXXXXXXXXXX")'''
    assert result == expected
    
def test_non_f_string():
    code = 'call(".2f")\n"""test"""'
    result = mask_str_in_code(code)
    assert result == 'call("XXX")\n"""XXXX"""'

def test_raw_string():
    code = r'path = r"C:\Users\test"'
    result = mask_str_in_code(code)
    assert result == r'path = r"XXXXXXXXXXXXX"'
    
def test_non_r_string():
    code = 'call(".2r")\n"""test"""'
    result = mask_str_in_code(code)
    assert result == 'call("XXX")\n"""XXXX"""'    

def test_custom_mask_char():
    code = "print('secret')"
    result = mask_str_in_code(code, mask_char='*')
    assert result == "print('******')"

def test_multiline_with_mixed_quotes():
    code = '''def example():
    s1 = "first string"
    s2 = 'second string'
    s3 = """multi
    line
    string"""
    return s1 + s2'''
    result = mask_str_in_code(code)
    expected = '''def example():
    s1 = "XXXXXXXXXXXX"
    s2 = 'XXXXXXXXXXXXX'
    s3 = """XXXXX
    XXXX
    XXXXXX"""
    return s1 + s2'''
    assert result == expected

def test_empty_string():
    code = 'x = ""'
    result = mask_str_in_code(code)
    assert result == 'x = ""'

def test_no_strings():
    code = '''def add(a, b):
    return a + b'''
    result = mask_str_in_code(code)
    assert result == code
