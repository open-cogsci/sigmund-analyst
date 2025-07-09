from pyqt_code_editor.utils.languages import python as python_utils


test_case = '''# %%
def test1():
    """Test function.
    """
    pass

#%%
def test2():
    """Test function.
    """
    pass
    
"""
Cell 3
"""
def test3():
    """Test function.
    """
    pass
    
\'\'\'
Cell 4
\'\'\'
def test4():
    """Test function.
    """
    pass
    
\"\"\"
Cell 5
\"\"\"
def test5():
    \'\'\'Test function.
    \'\'\'
    pass
    
\'\'\'
Cell 6
\'\'\'
def test6():
    \'\'\'Test function.
    \'\'\'
    pass
'''


def test_python_extract_cells_from_code():
    for cell in python_utils.extract_cells_from_code(test_case):
        print(cell)
        assert len(cell['code'].splitlines()) == 4
    
    
if __name__ == "__main__":
    test_python_extract_cells_from_code()
