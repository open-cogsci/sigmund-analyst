from qtpy.QtCore import Signal, QObject


class EnvironmentManager(QObject):
    """Singleton class to share the current environment and language between all
    components of the app.
    """    
    environment_changed = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.name = None
        self.path = None
        self.language = None

    @property
    def current_environment(self):
        return self.name, self.path, self.language

    def set_environment(self, name, path, language):
        if path != self.path:
            self.name = name
            self.path = path
            self.language = language
            self.environment_changed.emit(name, path, language)


# Singleton instance
environment_manager = EnvironmentManager()