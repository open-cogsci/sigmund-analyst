import os

# Worker
max_completions = 5

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
codestral_timeout = 1000
codestral_timeout_multiline = 5000

# Shortcuts mixin
shortcut_move_line_up = 'Alt+Up'
shortcut_move_line_down = 'Alt+Down'
shortcut_duplicate_line = 'Ctrl+D'

# Comment mixin
shortcut_comment = 'Ctrl+/'
