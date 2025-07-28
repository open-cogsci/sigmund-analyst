import os
from qtpy.QtCore import Signal, QObject
import logging
logger = logging.getLogger(__name__)

class EnvironmentManager(QObject):
    """Singleton class to share the current environment and language between all
    components of the app.
    """    
    environment_changed = Signal(str, str, str, str)

    def __init__(self):
        super().__init__()
        self.name = None
        self.path = None
        self.language = None
        self.prefix = None

    @property
    def current_environment(self):
        return self.name, self.path, self.language

    def set_environment(self, name, path, language, prefix=None):
        if path != self.path:
            # The path may not exist if the environment is simply python or 
            # python3, in which case we do not need to specify it at all.
            if not os.path.exists(path):
                path = None
            self.name = name
            self.path = path
            self.language = language
            self.prefix = prefix
            self.environment_changed.emit(name, path, language, prefix)


# Singleton instance
environment_manager = EnvironmentManager()