import asyncio
import json
import logging
import math
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import socketio

log = logging.getLogger(__name__)


class DashboardData:
    """Container for dashboard data with validation and default values."""
    
    def __init__(self):
        # Pump Control Data
        self.target_rate: float = 0.0
        self.flow_rate: float = 0.0
        self.pump_state: str = "standby"
        
        # Pump 2 Control Data
        self.pump2_target_rate: float = 0.0
        self.pump2_flow_rate: float = 0.0
        self.pump2_pump_state: str = "standby"
        
        # Solar Control Data
        self.battery_voltage: float = 0.0
        self.battery_percentage: float = 0.0
        self.panel_power: float = 0.0
        self.battery_ah: float = 0.0
        
        # Tank Control Data
        self.tank_level_mm: float = 0.0
        self.tank_level_percent: float = 0.0
        
        # Skid Control Data
        self.skid_flow: float = 0.0
        self.skid_pressure: float = 0.0
        
        # System Data
        self.timestamp: datetime = datetime.now()
        self.system_status: str = "running"
        
        # Fault Data
        self.faults = {
            "hh_pressure": False,
            "ll_tank_level": False
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pump": {
                "target_rate": self.target_rate,
                "flow_rate": self.flow_rate,
                "pump_state": self.pump_state
            },
            "pump2": {
                "target_rate": self.pump2_target_rate,
                "flow_rate": self.pump2_flow_rate,
                "pump_state": self.pump2_pump_state
            },
            "solar": {
                "battery_voltage": self.battery_voltage,
                "battery_percentage": self.battery_percentage,
                "panel_power": self.panel_power,
                "battery_ah": self.battery_ah
            },
            "tank": {
                "tank_level_mm": self.tank_level_mm,
                "tank_level_percent": self.tank_level_percent
            },
            "skid": {
                "skid_flow": self.skid_flow,
                "skid_pressure": self.skid_pressure
            },
            "system": {
                "timestamp": self.timestamp.isoformat(),
                "status": self.system_status
            },
            "faults": {
                "hh_pressure": self.faults["hh_pressure"],
                "ll_tank_level": self.faults["ll_tank_level"]
            }
        }
    
    @staticmethod
    def _to_bool(value: Any, default: bool = False) -> bool:
        """Convert a value to boolean with fallback."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return default
    
    def _update_numeric(self, attr: str, value: Any, tolerance: float = 0.0) -> bool:
        """Update a numeric attribute if it changes beyond tolerance."""
        if value is None:
            return False
        try:
            new_value = float(value)
        except (TypeError, ValueError):
            return False
        
        current_value = getattr(self, attr)
        if isinstance(current_value, (int, float)) and isinstance(new_value, (int, float)):
            if math.isfinite(current_value) and math.isfinite(new_value):
                if abs(current_value - new_value) <= tolerance:
                    return False
            elif current_value == new_value:
                return False
        elif current_value == new_value:
            return False
        
        setattr(self, attr, new_value)
        return True
    
    def _update_string(self, attr: str, value: Any) -> bool:
        """Update a string attribute if the value changed."""
        if value is None:
            return False
        new_value = str(value)
        current_value = getattr(self, attr)
        if current_value == new_value:
            return False
        setattr(self, attr, new_value)
        return True
    
    def update_from_dict(self, data: Dict[str, Any]) -> bool:
        """Update from dictionary with validation. Returns True if data changed."""
        changed = False
        
        if "pump" in data:
            pump = data["pump"]
            changed |= self._update_numeric("target_rate", pump.get("target_rate"), tolerance=0.05)
            changed |= self._update_numeric("flow_rate", pump.get("flow_rate"), tolerance=0.05)
            changed |= self._update_string("pump_state", pump.get("pump_state", self.pump_state))
        
        if "pump2" in data:
            pump2 = data["pump2"]
            changed |= self._update_numeric("pump2_target_rate", pump2.get("target_rate"), tolerance=0.05)
            changed |= self._update_numeric("pump2_flow_rate", pump2.get("flow_rate"), tolerance=0.05)
            changed |= self._update_string("pump2_pump_state", pump2.get("pump_state", self.pump2_pump_state))
        
        if "solar" in data:
            solar = data["solar"]
            changed |= self._update_numeric("battery_voltage", solar.get("battery_voltage"), tolerance=0.1)
            changed |= self._update_numeric("battery_percentage", solar.get("battery_percentage"), tolerance=0.2)
            changed |= self._update_numeric("panel_power", solar.get("panel_power"), tolerance=0.1)
            changed |= self._update_numeric("battery_ah", solar.get("battery_ah"), tolerance=0.1)
        
        if "tank" in data:
            tank = data["tank"]
            changed |= self._update_numeric("tank_level_mm", tank.get("tank_level_mm"), tolerance=1.0)
            changed |= self._update_numeric("tank_level_percent", tank.get("tank_level_percent"), tolerance=1)
        
        if "skid" in data:
            skid = data["skid"]
            changed |= self._update_numeric("skid_flow", skid.get("skid_flow"), tolerance=0.1)
            changed |= self._update_numeric("skid_pressure", skid.get("skid_pressure"), tolerance=10)
        
        if "system" in data:
            system = data["system"]
            changed |= self._update_string("system_status", system.get("status", self.system_status))
        
        if "faults" in data:
            faults = data["faults"]
            if isinstance(faults, dict):
                if "hh_pressure" in faults:
                    new_value = self._to_bool(faults.get("hh_pressure"), self.faults["hh_pressure"])
                    if self.faults["hh_pressure"] != new_value:
                        self.faults["hh_pressure"] = new_value
                        changed = True
                if "ll_tank_level" in faults:
                    new_value = self._to_bool(faults.get("ll_tank_level"), self.faults["ll_tank_level"])
                    if self.faults["ll_tank_level"] != new_value:
                        self.faults["ll_tank_level"] = new_value
                        changed = True
        
        if changed:
            self.timestamp = datetime.now()
        return changed


class NAPDDashboard:
    """Flask dashboard with WebSocket support for SIA Local Control UI."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8092, debug: bool = False, interface=None):
        self.host = host
        self.port = port
        self.debug = debug
        self.interface = interface  # Reference to DashboardInterface
        
        # Create Flask app
        self.app = Flask(__name__, 
                        template_folder='templates',
                        static_folder='static')
        self.app.config['SECRET_KEY'] = 'sia_dashboard_secret_key'
        
        # Create SocketIO instance
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Dashboard data container
        self.data = DashboardData()
        
        # Connection tracking
        self.connected_clients = set()
        
        # Setup routes and event handlers
        self._setup_routes()
        self._setup_socket_events()
        
        # Background thread for data updates
        self._update_thread = None
        self._running = False
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            return render_template('dashboard.html')
        
        @self.app.route('/api/data')
        def get_data():
            """REST API endpoint to get current data."""
            return self.data.to_dict()
        
        @self.app.route('/api/health')
        def health():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    def _setup_socket_events(self):
        """Setup WebSocket event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            self.connected_clients.add(request.sid)
            log.info(f"Client connected: {request.sid}")
            log.info(f"Total connected clients: {len(self.connected_clients)}")
            
            # Send current data to newly connected client
            emit('data_update', self.data.to_dict())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            self.connected_clients.discard(request.sid)
            log.info(f"Client disconnected: {request.sid}")
            log.info(f"Total connected clients: {len(self.connected_clients)}")
        
        @self.socketio.on('request_data')
        def handle_data_request():
            """Handle explicit data request from client."""
            emit('data_update', self.data.to_dict())
        
        @self.socketio.on('request_pump_selection')
        def handle_pump_selection_request():
            """Handle pump selection request from client."""
            if self.interface:
                # Get current pump selection from interface
                selected_pump = self.interface.getSelectedPump()
                emit('pump_selection_changed', {
                    'selected_pump': selected_pump,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                # Fallback to default
                emit('pump_selection_changed', {
                    'selected_pump': 1,  # Default to pump 1
                    'timestamp': datetime.now().isoformat()
                })
        
        @self.socketio.on('set_pump_state')
        def handle_pump_state_change(data):
            """Handle pump state change from client."""
            try:
                if 'state' in data:
                    self.data.pump_state = str(data['state'])
                    self.data.timestamp = datetime.now()
                    log.info(f"Pump state changed to: {self.data.pump_state}")
                    
                    # Broadcast update to all clients
                    self.broadcast_update()
            except Exception as e:
                log.error(f"Error handling pump state change: {e}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('toggle_selected_pump')
        def handle_toggle_selected_pump():
            """Handle pump selection toggle from client."""
            try:
                # Emit a response that the client can handle
                emit('pump_selection_toggled', {'message': 'Pump selection toggle requested'})
                log.info("Pump selection toggle requested from client")
            except Exception as e:
                log.error(f"Error handling pump selection toggle: {e}")
                emit('error', {'message': str(e)})
    
    def broadcast_update(self):
        """Broadcast data update to all connected clients."""
        if self.connected_clients:
            self.socketio.emit('data_update', self.data.to_dict())
    
    def update_data(self, **kwargs):
        """Update dashboard data and broadcast to clients."""
        try:
            # Update data container
            if kwargs:
                if self.data.update_from_dict(kwargs):
                    self.broadcast_update()
                    log.debug(f"Dashboard data updated: {kwargs}")
        except Exception as e:
            log.error(f"Error updating dashboard data: {e}")
    
    def start(self):
        """Start the dashboard server."""
        log.info(f"Starting SIA Dashboard on {self.host}:{self.port}")
        self._running = True
        
        # Start background update thread
        self._update_thread = threading.Thread(target=self._background_updates, daemon=True)
        self._update_thread.start()
        
        # Start Flask-SocketIO server (disable debug mode for threading compatibility)
        self.socketio.run(self.app, host=self.host, port=self.port, debug=False, allow_unsafe_werkzeug=True)
    
    def _background_updates(self):
        """Background thread for periodic updates and health monitoring."""
        while self._running:
            try:
                # Update system timestamp
                self.data.timestamp = datetime.now()
                
                # Send periodic heartbeat to clients
                if self.connected_clients:
                    self.socketio.emit('heartbeat', {'timestamp': self.data.timestamp.isoformat()})
                
                time.sleep(1)  # Update every second
            except Exception as e:
                log.error(f"Error in background updates: {e}")
                time.sleep(5)
    
    def stop(self):
        """Stop the dashboard server."""
        log.info("Stopping SIA Dashboard")
        self._running = False
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=5)


class DashboardInterface:
    """Interface class to integrate dashboard with Application class."""
    
    def __init__(self, dashboard: NAPDDashboard = None):
        if dashboard is None:
            # Create dashboard with reference to this interface
            self.dashboard = NAPDDashboard(interface=self)
        else:
            self.dashboard = dashboard
            # Set the interface reference in the dashboard
            self.dashboard.interface = self
        
        self._server_thread = None
        self.selected_pump = 1  # Default to pump 1
    
    def start_dashboard(self):
        """Start dashboard in a separate thread."""
        if self._server_thread and self._server_thread.is_alive():
            log.warning("Dashboard is already running")
            return
        
        self._server_thread = threading.Thread(target=self._dashboard_thread_start, daemon=True)
        self._server_thread.start()
        log.info("Dashboard started in background thread")
        
        # Broadcast initial pump selection after a short delay
        threading.Timer(2.0, self.broadcast_pump_selection).start()
    
    def _dashboard_thread_start(self):
        """Thread-safe dashboard startup."""
        try:
            self.dashboard.start()
        except Exception as e:
            log.error(f"Dashboard startup failed: {e}")
            # Dashboard will fall back gracefully
    
    def stop_dashboard(self):
        """Stop the dashboard."""
        self.dashboard.stop()
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=5)
        log.info("Dashboard stopped")
        
    def set_faults(self, hh_pressure: bool = False, ll_tank_level: bool = False):
        """Set faults."""
        self.dashboard.update_data(faults={'hh_pressure': hh_pressure, 'll_tank_level': ll_tank_level})
    
    def clear_faults(self):
        """Clear faults."""
        self.set_faults(hh_pressure=False, ll_tank_level=False)
    
    def update_pump_data(self, target_rate: float = None, flow_rate: float = None, pump_state: str = None):
        """Update pump control data."""
        pump_data = {}
        if target_rate is not None:
            pump_data['target_rate'] = target_rate
        if flow_rate is not None:
            pump_data['flow_rate'] = flow_rate
        if pump_state is not None:
            pump_data['pump_state'] = pump_state
        
        if pump_data:
            self.dashboard.update_data(pump=pump_data)
    
    def update_pump2_data(self, target_rate: float = None, flow_rate: float = None, pump_state: str = None):
        """Update pump 2 control data."""
        pump2_data = {}
        if target_rate is not None:
            pump2_data['target_rate'] = target_rate
        if flow_rate is not None:
            pump2_data['flow_rate'] = flow_rate
        if pump_state is not None:
            pump2_data['pump_state'] = pump_state
        
        if pump2_data:
            self.dashboard.update_data(pump2=pump2_data)
    
    def update_solar_data(self, battery_voltage: float = None, battery_percentage: float = None, array_voltage: float = None, battery_ah: float = None):
        """Update solar control data."""
        solar_data = {}
        if battery_voltage is not None:
            solar_data['battery_voltage'] = battery_voltage
        if battery_percentage is not None:
            solar_data['battery_percentage'] = battery_percentage
        if array_voltage is not None:
            solar_data['panel_power'] = array_voltage  # array_voltage parameter now contains panel_power
        if battery_ah is not None:
            solar_data['battery_ah'] = battery_ah
        
        if solar_data:
            self.dashboard.update_data(solar=solar_data)
    
    def update_tank_data(self, tank_level_mm: float = None, tank_level_percent: float = None):
        """Update tank control data."""
        tank_data = {}
        if tank_level_mm is not None:
            tank_data['tank_level_mm'] = tank_level_mm
        if tank_level_percent is not None:
            tank_data['tank_level_percent'] = tank_level_percent
        
        if tank_data:
            self.dashboard.update_data(tank=tank_data)
    
    def update_skid_data(self, skid_flow: float = None, skid_pressure: float = None):
        """Update skid control data."""
        skid_data = {}
        if skid_flow is not None:
            skid_data['skid_flow'] = skid_flow
        if skid_pressure is not None:
            skid_data['skid_pressure'] = skid_pressure
        
        if skid_data:
            self.dashboard.update_data(skid=skid_data)
    
    def update_system_status(self, status: str):
        """Update system status."""
        self.dashboard.update_data(system={'status': status})
    
    def toggleSelectedPump(self):
        """Toggle between pump 1 and pump 2 selection."""
        self.selected_pump = 2 if self.selected_pump == 1 else 1
        log.info(f"Selected pump changed to: {self.selected_pump}")
        
        # Emit WebSocket event to update all connected clients
        self.dashboard.socketio.emit('pump_selection_changed', {
            'selected_pump': self.selected_pump,
            'timestamp': datetime.now().isoformat()
        })
        
        return self.selected_pump
    
    def getSelectedPump(self):
        """Get the currently selected pump number."""
        return self.selected_pump
    
    def setSelectedPump(self, pump_number: int):
        """Set the selected pump number (1 or 2)."""
        if pump_number in [1, 2]:
            self.selected_pump = pump_number
            log.info(f"Selected pump set to: {self.selected_pump}")
            
            # Emit WebSocket event to update all connected clients
            self.dashboard.socketio.emit('pump_selection_changed', {
                'selected_pump': self.selected_pump,
                'timestamp': datetime.now().isoformat()
            })
        else:
            log.error(f"Invalid pump number: {pump_number}. Must be 1 or 2.")
        return self.selected_pump
    
    def broadcast_pump_selection(self):
        """Broadcast current pump selection to all connected clients."""
        self.dashboard.socketio.emit('pump_selection_changed', {
            'selected_pump': self.selected_pump,
            'timestamp': datetime.now().isoformat()
        })
        log.info(f"Broadcasted pump selection: {self.selected_pump}")
    
    def updateSelectedTargetRate(self, value: float):
        """Update the target rate of the currently selected pump."""
        try:
            if self.selected_pump == 1:
                self.update_pump_data(target_rate=value)
            elif self.selected_pump == 2:
                self.update_pump2_data(target_rate=value)
            else:
                log.error(f"Invalid selected pump: {self.selected_pump}")
                return False
            
            log.info(f"Updated pump {self.selected_pump} target rate to: {value}")
            return True
        except Exception as e:
            log.error(f"Error updating target rate for pump {self.selected_pump}: {e}")
            return False
    
    def updateSelectedPumpState(self, state: str):
        """Update the state of the currently selected pump.
        
        Args:
            state: Either "pumping" or "standby"
        """
        try:
            # Validate state
            if state not in ["pumping", "standby"]:
                log.error(f"Invalid pump state: {state}. Must be 'pumping' or 'standby'")
                return False
            
            if self.selected_pump == 1:
                self.update_pump_data(pump_state=state)
            elif self.selected_pump == 2:
                self.update_pump2_data(pump_state=state)
            else:
                log.error(f"Invalid selected pump: {self.selected_pump}")
                return False
            
            log.info(f"Updated pump {self.selected_pump} state to: {state}")
            return True
        except Exception as e:
            log.error(f"Error updating state for pump {self.selected_pump}: {e}")
            return False
