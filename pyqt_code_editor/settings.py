import os

# Appearance
font_size = 16
font_family = 'Ubuntu Mono'
color_scheme = 'monokai'
tab_width = 4
word_wrap = False
character_ruler = 80  # None to disable
search_replace_background = "#fdff74"
search_replace_foreground = "#000000"

# The current folder is the home folder by default, but will be updated as the
# user saves and opens files.
current_folder = os.path.expanduser('~')
default_filename = 'untitled.txt'
default_encoding = 'utf-8'

# Keyboard shortcuts
shortcut_move_line_up = 'Alt+Up'
shortcut_move_line_down = 'Alt+Down'
shortcut_duplicate_line = 'Ctrl+D'
shortcut_comment = 'Ctrl+/'
shortcut_split_horizontally = 'Ctrl+Shift+H'
shortcut_split_vertically = 'Ctrl+Shift+V'
shortcut_quick_open_file = 'Ctrl+P'
shortcut_symbols = 'Ctrl+R'
shortcut_previous_tab = 'Ctrl+Shift+Tab'
shortcut_close_all_tabs = 'Ctrl+Shift+W'
shortcut_close_other_tabs = 'Ctrl+Alt+W'
shortcut_open_folder = 'Ctrl+Shift+O'

# Project explorer
max_files = 1000

# Complete
max_completions = 5
full_completion_delay = 250
hide_completion_delay = 500

# Check
check_debounce_delay = 500
check_interval_delay = 5000

# Sigmund provider
sigmund_max_context = 2000
sigmund_fim_endpoint = 'http://localhost:5000/code_completion/fim'
sigmund_token = None
sigmund_timeout = 1  # seconds

# Codestral provider
codestral_max_context = 2000
codestral_min_context = 100
codestral_model = 'codestral-latest'
codestral_api_key = os.environ.get('CODESTRAL_API_KEY')
codestral_url = 'https://codestral.mistral.ai'
codestral_timeout = 5000
