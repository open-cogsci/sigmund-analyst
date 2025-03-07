import inspect
from qtpy.QtCore import QObject, Signal
import logging

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


class SignalRouter(QObject):
    """
    A central signal router that dynamically discovers and forwards signals.
    """
    # Generic signal that forwards all signals with metadata
    signal_triggered = Signal(str, object)
    
    def __init__(self):
        super().__init__()
        self._registered_widgets = set()
        self._signal_map = {}  # Maps signal names to widgets
        self._connections = {}  # Maps widget IDs to connection info
        logger.info("Signal router initialized")
        
    def register_widget(self, widget):
        """Register a widget and all its signals for routing"""
        if widget in self._registered_widgets:
            return
            
        self._registered_widgets.add(widget)
        widget_id = id(widget)
        self._connections[widget_id] = []
        
        # Connect to destroyed signal for auto cleanup
        widget.destroyed.connect(lambda: self.unregister_widget(widget))
        
        logger.info(f"Registering widget {widget.__class__.__name__} for signal routing")
        
        # Discover all signals in the widget
        for name, obj in inspect.getmembers(widget.__class__):
            if isinstance(obj, Signal):
                logger.info(f"  Discovered signal: {name}")
                self._signal_map[name] = self._signal_map.get(name, []) + [widget]
                
                # Create a forwarder function that will be connected to the signal
                def create_forwarder(signal_name=name):
                    forwarder = lambda *args: self.signal_triggered.emit(signal_name, args)
                    return forwarder
                
                forwarder = create_forwarder()
                
                # Connect the widget's signal to our forwarder
                try:
                    signal = getattr(widget, name)
                    signal.connect(forwarder)
                    
                    # Store connection information for cleanup
                    self._connections[widget_id].append({
                        'signal': signal,
                        'slot': forwarder,
                        'name': name
                    })
                except (RuntimeError, TypeError) as e:
                    logger.warning(f"Failed to connect to signal {name}: {e}")
    
    def unregister_widget(self, widget):
        """Unregister a widget and disconnect all its signals"""
        widget_id = id(widget)
        
        if widget_id in self._connections:
            logger.info(f"Unregistering widget {widget.__class__.__name__}")
            
            # Disconnect all signals from this widget
            for connection in self._connections[widget_id]:
                try:
                    connection['signal'].disconnect(connection['slot'])
                    logger.debug(f"Disconnected signal {connection['name']}")
                except (RuntimeError, TypeError):
                    # Signal might already be disconnected or invalid
                    pass
            
            # Clean up our data structures
            del self._connections[widget_id]
            
            # Update signal map to remove this widget
            for signal_name, widgets in list(self._signal_map.items()):
                self._signal_map[signal_name] = [w for w in widgets if id(w) != widget_id]
                # Remove empty entries
                if not self._signal_map[signal_name]:
                    del self._signal_map[signal_name]
            
            # Try to remove from registered widgets
            try:
                self._registered_widgets.remove(widget)
            except KeyError:
                pass
        
    def connect_to_signal(self, signal_name, slot):
        """
        Connect a slot to a specific named signal from any registered widget
        """
        def filtered_forwarder(name, args):
            if name == signal_name:
                # Use *args to unpack the arguments
                if len(args) == 1:
                    slot(args[0])
                else:
                    slot(*args)
                    
        self.signal_triggered.connect(filtered_forwarder)
        logger.info(f"Connected external slot to '{signal_name}' signal")
        
    def get_available_signals(self):
        """Return a list of all available signals from registered widgets"""
        return list(self._signal_map.keys())


signal_router = SignalRouter()