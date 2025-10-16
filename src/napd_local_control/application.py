import logging
import time

from pydoover.docker import Application
from pydoover import ui

from .app_config import NapdLocalControlConfig
from .dashboard import NAPDDashboard, DashboardInterface

log = logging.getLogger()

class NapdLocalControlApplication(Application):
    config: NapdLocalControlConfig  # not necessary, but helps your IDE provide autocomplete!

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.started: float = time.time()
        
        # Initialize dashboard
        self.dashboard = NAPDDashboard(host="0.0.0.0", port=8092, debug=False)
        self.dashboard_interface = DashboardInterface(self.dashboard)

    async def setup(self):
        self.loop_target_period = 0.2
        
        # Start dashboard
        self.dashboard_interface.start_dashboard()
        log.info("Dashboard started on port 8092")

    async def main_loop(self):
        
        # self.get_tag("tank_level", self.config.tank_level_app.value)
        # a random value we set inside our simulator. Go check it out in simulators/sample!
        # Update dashboard with example data
        await self.update_dashboard_data()
    
    async def update_dashboard_data(self):
        """Update dashboard with data from various sources."""
        # try:
            # Get pump control data from simulators
        target_rate = self.get_tag("TargetRate", self.config.pump_controllers.elements[0].value) if self.config.pump_controllers else 15.5
        flow_rate = self.get_tag("FlowRate", self.config.pump_controllers.elements[0].value) if self.config.pump_controllers else 14.2
        pump_state = self.get_tag("StateString", self.config.pump_controllers.elements[0].value) if self.config.pump_controllers else "auto"
        
        # Update pump data
        self.dashboard_interface.update_pump_data(
            target_rate=target_rate,
            flow_rate=flow_rate,
            pump_state=pump_state
        )
        
        # Get pump 2 control data from simulators
        if len(self.config.pump_controllers.elements) > 1:
            pump2_target_rate = self.get_tag("TargetRate", self.config.pump_controllers.elements[1].value)
            pump2_flow_rate = self.get_tag("FlowRate", self.config.pump_controllers.elements[1].value)
            pump2_pump_state = self.get_tag("StateString", self.config.pump_controllers.elements[1].value)
        else:
            # Fallback values for pump 2 if not configured
            pump2_target_rate = "-"
            pump2_flow_rate = "-"
            pump2_pump_state = "-"
        
        # Update pump 2 data
        self.dashboard_interface.update_pump2_data(
            target_rate=pump2_target_rate,
            flow_rate=pump2_flow_rate,
            pump_state=pump2_pump_state
        )
        
        # Get and aggregate solar control data from all simulators
        if self.config.solar_controllers:
            battery_voltages = []
            battery_percentages = []
            panel_power_values = []
            battery_ah_values = []
            
            # Collect data from all solar controllers
            for solar_controller in self.config.solar_controllers.elements:
                r = self.get_tag("b_voltage", solar_controller.value)
                if r is not None:
                    battery_voltages.append(r)
                r = self.get_tag("b_percent", solar_controller.value)
                if r is not None:
                    battery_percentages.append(r)
                r = self.get_tag("panel_power", solar_controller.value)
                if r is not None:
                    panel_power_values.append(r)
                r = self.get_tag("remaining_ah", solar_controller.value)
                if r is not None:
                    battery_ah_values.append(r)
            
            # Aggregate data: average voltages/percentages, sum battery_ah
            if len(battery_voltages) > 0:
                battery_voltage = sum(battery_voltages) / len(battery_voltages)
            else:
                battery_voltage = 0.0
            if len(battery_percentages) > 0:
                battery_percentage = sum(battery_percentages) / len(battery_percentages)
            else:
                battery_percentage = 0.0
            if len(panel_power_values) > 0:
                panel_power = sum(panel_power_values) / len(panel_power_values)
            else:
                panel_power = 0.0
            
            if len(battery_ah_values) > 0:
                battery_ah = sum(battery_ah_values) 
            else:
                battery_ah = 0.0
            
        else:
            # Fallback values if no solar controllers configured
            battery_voltage = 24.5
            battery_percentage = 78.0
            panel_power = 150.0
            battery_ah = 120.0
        
        # Update solar data
        self.dashboard_interface.update_solar_data(
            battery_voltage=battery_voltage,
            battery_percentage=battery_percentage,
            array_voltage=panel_power,
            battery_ah=battery_ah
        )
        
        # Get tank control data from simulators
        tank_level_m = self.get_tag("level_reading", self.config.tank_level_app.value) if self.config.tank_level_app.value else None
        tank_level_mm = None
        if tank_level_m is not None:
            tank_level_mm = tank_level_m * 1000
        tank_level_percent = self.get_tag("level_filled_percentage", self.config.tank_level_app.value) if self.config.tank_level_app.value else None
        
        # Update tank data
        self.dashboard_interface.update_tank_data(
            tank_level_mm=tank_level_mm,
            tank_level_percent=tank_level_percent
        )
        
        self.dashboard_interface.update_skid_data(
            skid_flow=self.get_tag("value", self.config.flow_sensor_app.value),
            skid_pressure=self.get_tag("value", self.config.pressure_sensor_app.value)
        )
            
            # Update system status
            # system_status = "running" if self.state.state == "on" else "standby"
            # self.dashboard_interface.update_system_status(system_status)
            
        # except Exception as e:
        #     log.error(f"Error updating dashboard data: {e}")
        #     # Use fallback data if simulators are not available
        #     self.update_dashboard_with_fallback_data()