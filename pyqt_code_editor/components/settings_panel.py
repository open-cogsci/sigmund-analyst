from qtpy.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                           QCheckBox, QSpinBox, QLineEdit, QPushButton, 
                           QGroupBox, QFormLayout, QScrollArea)
from .. import settings, themes
from ..widgets import Dock
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SettingsWidget(QWidget):    
    """Implements a basic dynamic settings panel. The settings can be retrieved like
    so:
    
    ```
    for setting, value in settings:
        pass
    ```
    
    And settings can be dynamically changed, like so: `settings.my_setting = 10`.
    There should also be a reset button that calls `settings.reset_to_defaults()`.
    
    You can assume that the current value of a setting determines its type. That
    is, if the value is an int, then it can only be changed to another int. Possible
    types are int, bool and str.    
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()
        
        # Connect to settings changes to update UI
        settings.setting_changed.connect(self.on_setting_changed)
        
        logger.info("Settings panel initialized")
    
    def setup_ui(self):
        """Create the basic UI structure"""
        logger.debug("Setting up settings panel UI")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(*themes.OUTER_CONTENT_MARGINS)
        
        # Create a scroll area for the settings
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        
        # Add scroll area to main layout
        self.main_layout.addWidget(self.scroll_area)
        
        # Create a button layout at the bottom
        self.button_layout = QHBoxLayout()
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self.reset_settings)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.reset_button)
        
        self.main_layout.addLayout(self.button_layout)
        
        # Dictionary to keep track of our UI elements for each setting
        self.setting_widgets = {}
    
    def load_settings(self):
        """Load all settings and create UI elements for them"""
        logger.info("Loading settings into UI")
        
        # Get settings grouped by category
        categories = settings.get_settings_by_category()
        
        # Create a form for each category
        for category, setting_names in categories.items():
            if not setting_names:
                continue
                
            group_box = QGroupBox(category)
            form_layout = QFormLayout(group_box)
            form_layout.setContentsMargins(*themes.OUTER_CONTENT_MARGINS)
            
            for setting_name in setting_names:
                value = getattr(settings, setting_name)
                widget = self.create_widget_for_setting(setting_name, value)
                
                if widget:
                    form_layout.addRow(setting_name.replace('_', ' ').title() + ":", widget)
                    self.setting_widgets[setting_name] = widget
            
            self.scroll_layout.addWidget(group_box)
        
        self.scroll_layout.addStretch()
    
    def create_widget_for_setting(self, setting_name, value):
        """Create appropriate widget based on setting type"""
        logger.debug(f"Creating widget for setting {setting_name} with value {value}")
        
        if isinstance(value, bool):
            widget = QCheckBox()
            widget.setChecked(value)
            widget.stateChanged.connect(lambda state, name=setting_name: 
                                       self.update_setting(name, bool(state)))
            
        elif isinstance(value, int):
            widget = QSpinBox()
            widget.setRange(-9999, 9999)  # Reasonable default range
            widget.setValue(value)
            widget.valueChanged.connect(lambda val, name=setting_name: 
                                       self.update_setting(name, val))
            
        elif isinstance(value, str):
            widget = QLineEdit(value)
            widget.textChanged.connect(lambda text, name=setting_name: 
                                      self.update_setting(name, text))
            
        else:
            logger.warning(f"Unsupported setting type for {setting_name}: {type(value)}")
            return None
            
        return widget
    
    def update_setting(self, setting_name, value):
        """Update a setting value"""
        current_value = getattr(settings, setting_name)
        
        # Only update if the value has actually changed
        # This avoids infinite loops when settings.setting_changed triggers
        if current_value != value:
            logger.info(f"Updating setting {setting_name} to {value}")
            setattr(settings, setting_name, value)
    
    def on_setting_changed(self, name, value):
        """Called when a setting changes to update the UI"""
        logger.debug(f"Setting changed: {name} = {value}")
        
        # If we have a widget for this setting, update it
        if name in self.setting_widgets:
            widget = self.setting_widgets[name]
            
            # Block signals to prevent infinite loops
            widget.blockSignals(True)
            
            if isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QSpinBox):
                widget.setValue(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)
                
            widget.blockSignals(False)
    
    def reset_settings(self):
        """Reset all settings to their default values"""
        logger.info("Resetting all settings to defaults")
        settings.reset_to_defaults()
        
        
class SettingsPanel(Dock):
    def __init__(self, parent):
        super().__init__('Settings', parent)
        self.setObjectName("Settings")
        self.setWidget(SettingsWidget(self))
