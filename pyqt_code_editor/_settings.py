import os
import json
from qtpy.QtCore import QObject, Signal, QSettings
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SettingProperty:
    """
    Descriptor for setting properties that emit signals when changed.
    
    This class uses Python's descriptor protocol to allow settings to be accessed
    like normal attributes (settings.font_size) while providing custom behavior
    when they are accessed or modified.
    """
    def __init__(self, default_value, category: str = "General"):
        self.name = None  # Will be set when the class is created
        self.default_value = default_value
        self.category = category
        
    def __set_name__(self, owner, name):
        """Called when the descriptor is assigned to a class attribute"""
        self.name = name
        
    def __get__(self, instance, owner):
        """
        Called when the attribute is accessed (settings.font_size)
        
        This is why settings.font_size returns an int instead of a SettingProperty.
        When you access settings.font_size, Python calls this method instead of
        returning the descriptor object itself.
        
        Args:
            instance: The Settings instance (or None if accessed from the class)
            owner: The Settings class
            
        Returns:
            The actual setting value (not the descriptor)
        """
        if instance is None:
            return self  # When accessed from the class (Settings.font_size), return the descriptor
        return instance._values.get(self.name, self.default_value)
        
    def __set__(self, instance, value):
        """Called when the attribute is set (settings.font_size = 18)"""
        old_value = self.__get__(instance, type(instance))
        if old_value != value:
            instance._values[self.name] = value
            logger.info(f"Setting changed: {self.name} = {value} (was {old_value})")
            instance.setting_changed.emit(self.name, value)


class Settings(QObject):
    """Qt-based settings class with change signals and persistence"""
    
    # Signal emitted when any setting changes: (setting_name, new_value)
    setting_changed = Signal(str, object)
    
    def __init__(self):        
        super().__init__()
        self._values = {}
        self._qsettings = QSettings("cogscinl", "Sigmund Analyst")
        logger.info("Initializing Settings manager")
        self._load_settings()
    
    # Appearance
    font_size = SettingProperty(16, "Appearance")
    font_family = SettingProperty('default', "Appearance")
    color_scheme = SettingProperty('monokai', "Appearance")
    tab_width = SettingProperty(4, "Appearance")
    default_indent = SettingProperty('\t', "Appearance")
    word_wrap = SettingProperty(False, "Appearance")
    character_ruler = SettingProperty(80, "Appearance")  # None to disable
    search_replace_background = SettingProperty("#fdff74", "Appearance")
    search_replace_foreground = SettingProperty("#000000", "Appearance")
    
    # Files and Folders
    current_folder = SettingProperty(os.path.expanduser('~'), "Files")
    default_filename = SettingProperty('untitled.txt', "Files")
    default_language = SettingProperty('python', "Files")
    default_encoding = SettingProperty('utf-8', "Files")
    
    # Keyboard shortcuts
    shortcut_move_line_up = SettingProperty('Alt+Up', "Shortcuts")
    shortcut_move_line_down = SettingProperty('Alt+Down', "Shortcuts")
    shortcut_duplicate_line = SettingProperty('Ctrl+D', "Shortcuts")
    shortcut_comment = SettingProperty('Ctrl+/', "Shortcuts")
    shortcut_split_horizontally = SettingProperty('Ctrl+Shift+H', "Shortcuts")
    shortcut_split_vertically = SettingProperty('Ctrl+Shift+V', "Shortcuts")
    shortcut_quick_open_file = SettingProperty('Ctrl+P', "Shortcuts")
    shortcut_symbols = SettingProperty('Ctrl+R', "Shortcuts")
    shortcut_previous_tab = SettingProperty('Ctrl+Shift+Tab', "Shortcuts")
    shortcut_close_all_tabs = SettingProperty('Ctrl+Shift+W', "Shortcuts")
    shortcut_close_other_tabs = SettingProperty('Ctrl+Alt+W', "Shortcuts")
    shortcut_open_folder = SettingProperty('Ctrl+Shift+O', "Shortcuts")
    shortcut_find_in_files = SettingProperty('Ctrl+Shift+F', "Shortcuts")
    shortcut_execute_code = SettingProperty('F9', "Shortcuts")
    shortcut_execute_file = SettingProperty('F5', "Shortcuts")
    shortcut_toggle_jupyter_console = SettingProperty('Ctrl+Shift+J', "Shortcuts")
    shortcut_toggle_sigmund = SettingProperty('Ctrl+Shift+I', "Shortcuts")
    shortcut_toggle_workspace_explorer = SettingProperty('Ctrl+Shift+X', "Shortcuts")
    shortcut_toggle_project_explorers = SettingProperty('Ctrl+\\', "Shortcuts")
    
    # Project explorer
    max_files = SettingProperty(1000, "ProjectExplorer")
    ignored_folders = SettingProperty(['.git'], "ProjectExplorer")
    
    # Completions
    max_completions = SettingProperty(5, "Completion")
    full_completion_delay = SettingProperty(250, "Completion")
    hide_completion_delay = SettingProperty(500, "Completion")
    
    # Code checking
    check_debounce_delay = SettingProperty(500, "Checking")
    check_interval_delay = SettingProperty(5000, "Checking")
    
    # Sigmund provider
    sigmund_max_context = SettingProperty(2000, "Sigmund")
    sigmund_fim_endpoint = SettingProperty('http://localhost:5000/code_completion/fim', "Sigmund")
    sigmund_token = SettingProperty(None, "Sigmund")
    sigmund_timeout = SettingProperty(1, "Sigmund")  # seconds
    
    # Codestral provider
    codestral_max_context = SettingProperty(2000, "Codestral")
    codestral_min_context = SettingProperty(100, "Codestral")
    codestral_model = SettingProperty('codestral-latest', "Codestral")
    codestral_api_key = SettingProperty(os.environ.get('CODESTRAL_API_KEY', ''), "Codestral")
    codestral_url = SettingProperty('https://codestral.mistral.ai', "Codestral")
    codestral_timeout = SettingProperty(5000, "Codestral")
    
    # Window geometry
    window_geometry = SettingProperty('', "Window")
    window_state = SettingProperty('', "Window")
    
    def save(self):
        """Save all settings to persistent storage"""
        logger.info("Saving settings to persistent storage")
        for setting_name, value in self._values.items():
            self._qsettings.setValue(setting_name, value)
        self._qsettings.sync()
        logger.info(f"Saved {len(self._values)} settings")
    
    def _load_settings(self):
        """Load settings from persistent storage"""
        logger.info("Loading settings from persistent storage")
        setting_names = self.get_all_setting_names()
        loaded_count = 0
        
        for setting_name in setting_names:
            if self._qsettings.contains(setting_name):
                value = self._qsettings.value(setting_name)
                # Convert the value back to the correct type based on default
                default = getattr(type(self), setting_name).default_value
                
                if isinstance(default, bool) and not isinstance(value, bool):
                    value = value.lower() == 'true'
                elif isinstance(default, int) and not isinstance(value, int):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to convert setting '{setting_name}' value to int: {value}")
                        value = default
                elif isinstance(default, float) and not isinstance(value, float):
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to convert setting '{setting_name}' value to float: {value}")
                        value = default
                
                self._values[setting_name] = value
                loaded_count += 1
                logger.info(f"Loaded setting: {setting_name} = {value}")
        
        logger.info(f"Loaded {loaded_count} settings ({len(setting_names) - loaded_count} using defaults)")
    
    def reset_to_defaults(self):
        """Reset all settings to their default values"""
        logger.info("Resetting all settings to defaults")
        self._values.clear()
        self.save()
        for setting_name in self.get_all_setting_names():
            # Access each property to trigger signal emission with default value
            default_value = getattr(type(self), setting_name).default_value
            logger.info(f"Reset setting: {setting_name} = {default_value} (default)")
            self.setting_changed.emit(setting_name, default_value)
    
    def get_all_setting_names(self) -> list[str]:
        """Get a list of all setting names"""
        names = [name for name, attr in vars(type(self)).items() 
                if isinstance(attr, SettingProperty)]
        logger.info(f"Found {len(names)} settings in total")
        return names
    
    def get_settings_by_category(self) -> dict[str, list[str]]:
        """Get a dictionary of settings grouped by category"""
        result = {}
        for name, attr in vars(type(self)).items():
            if isinstance(attr, SettingProperty):
                category = attr.category
                if category not in result:
                    result[category] = []
                result[category].append(name)
        
        categories_count = len(result)
        logger.info(f"Settings organized into {categories_count} categories")
        return result
        
    def __iter__(self):
        """Iterate over all settings"""
        for name in self.get_all_setting_names():
            yield name, getattr(self, name)
        
    def __str__(self):
        """Returns all settings as a JSON array of objects."""
        # todo
        return json.dumps({name: value for name, value in self})
        
    def set_font_family(self):
        """Changes the font family from default to an actual font. This happens
        only after the app has been initialized, because QFontDatase requires
        a QApplication instance.
        """
        if self.font_family != 'default':
            return
        from .utils import get_first_available_font
        self.font_family = get_first_available_font(
            ['Ubuntu Mono', 'Liberation Mono', 'DejaVu Sans Mono', 'Courier New',
             'monospace'])
        logger.info(f'setting font family to {self.font_family}')


# Create the singleton instance
settings = Settings()
