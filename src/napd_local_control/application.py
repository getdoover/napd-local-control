import logging
import time

from pydoover.docker import Application
from pydoover import ui
from pydoover.utils.kalman import apply_async_kalman_filter

from .app_config import NapdLocalControlConfig, EdgeChoice
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
        
        #for catching the first event that is triggered when pulse counter starts
        self.start_first_callback = False
        
        self.hh_pressure_active = False
        self.ll_tank_level_active = False

    async def setup(self):
        self.loop_target_period = 0.2
        
        # Start dashboard
        self.dashboard_interface.start_dashboard()
        
        ## create button and dial pulse counting subs
        
        self.selector_button = self.platform_iface.get_new_pulse_counter(
            di=self.config.selector_pin.value,
            edge="rising",
            callback=self.selector_button_callback,
            rate_window_secs=60,
        )
        
        edge = "VI+18" if self.config.start_pump_edge_rising else "VI-18"
        self.start_pump = self.platform_iface.get_new_pulse_counter(
            di=self.config.start_pump_pin.value,
            edge=edge,
            callback=self.start_pump_callback,
            rate_window_secs=60,
        )
        
        self.stop_pump = self.platform_iface.get_new_pulse_counter(
            di=self.config.stop_pump_pin.value,
            edge="rising",
            callback=self.stop_pump_callback,
            rate_window_secs=60,
        )
        
                
        self.last_ai_input = await self.platform_iface.get_ai(self.config.potentiometer_pin.value)
        
        log.info("Dashboard started on port 8092")

    async def main_loop(self):
        
        # self.get_tag("tank_level", self.config.tank_level_app.value)
        # a random value we set inside our simulator. Go check it out in simulators/sample!
        # Update dashboard with example data
        await self.check_faults()
        await self.update_target_rate()
        await self.update_dashboard_data()
        await self.update_pump_leds()
        
    async def check_faults(self):
        p1_app_state =self.get_tag("AppState", self.config.pump_1.value)
        p2_app_state =self.get_tag("AppState", self.config.pump_2.value)
        
        if "pressure_high_high_level" in (p1_app_state, p2_app_state):
            self.hh_pressure_active = True
        elif "tank_level_low_low_level" in (p1_app_state, p2_app_state):
            self.ll_tank_level_active = True
        
        self.dashboard_interface.set_faults(
            hh_pressure=self.hh_pressure_active,
            ll_tank_level=self.ll_tank_level_active
        )
        
    async def update_pump_leds(self):
        p1_state_string =self.get_tag("StateString", self.config.pump_1.value)
        p2_state_string =self.get_tag("StateString", self.config.pump_2.value)
        
        p1_led_state = self.get_tag(f"DO{self.config.pump_1_start_LED_pin.value}", "platform")
        p2_led_state = self.get_tag(f"DO{self.config.pump_2_start_LED_pin.value}", "platform")
        p1_fault_led_state = self.get_tag(f"AO{self.config.pump_1_fault_LED_pin.value}", "platform")
        p2_fault_led_state = self.get_tag(f"AO{self.config.pump_2_fault_LED_pin.value}", "platform")
        
        # Update fault LED
        if p1_fault_led_state is not None and p2_fault_led_state is not None:
            if (self.hh_pressure_active or self.ll_tank_level_active):
                if float(p1_fault_led_state) < 0.1 or float(p2_fault_led_state) < 0.1:
                    print("setting fault leds to 100")
                    await self.platform_iface.set_ao(self.config.pump_1_fault_LED_pin.value, 100)
                    await self.platform_iface.set_ao(self.config.pump_2_fault_LED_pin.value, 100)
            elif p1_fault_led_state > 0 or p2_fault_led_state > 0:
                await self.platform_iface.set_ao(self.config.pump_1_fault_LED_pin.value, 0)
                await self.platform_iface.set_ao(self.config.pump_2_fault_LED_pin.value, 0)
        
        if p1_state_string  == "pumping":
            if not p1_led_state:
                await self.platform_iface.set_do(self.config.pump_1_start_LED_pin.value, True)
        elif p1_state_string == "standby":
            if p1_led_state:
                await self.platform_iface.set_do(self.config.pump_1_start_LED_pin.value, False)
                
        if p2_state_string == "pumping":
            if not p2_led_state:
                await self.platform_iface.set_do(self.config.pump_2_start_LED_pin.value, True)
        elif p2_state_string == "standby":
            if p2_led_state:
                await self.platform_iface.set_do(self.config.pump_2_start_LED_pin.value, False)
        elif p2_state_string == "fault":
            pass
    async def update_target_rate(self):
        pump_number = self.dashboard_interface.getSelectedPump()
        ai_input = await self.get_pot_reading(kf_measurement_variance=0.0005)
        log.debug(f"AI Input: {ai_input}")
        if ai_input is not None and self.last_ai_input * 0.99 < ai_input < self.last_ai_input * 1.01:
            return
        
        sys_voltage = self.get_tag("voltage", "platform")
        if not sys_voltage:
            sys_voltage = 25.0
        target_rate = round(ai_input / sys_voltage * 100, 2)
        
        if pump_number == 1:
            await self.set_tag("TargetRatePercentage", target_rate, self.config.pump_1.value)
        elif pump_number == 2:
            await self.set_tag("TargetRatePercentage", target_rate, self.config.pump_2.value)
        self.last_ai_input = ai_input
        
    @apply_async_kalman_filter(process_variance=.01)
    async def get_pot_reading(self, kf_measurement_variance=1):
        ai_input = await self.platform_iface.get_ai(self.config.potentiometer_pin.value)
        log.debug(f"Raw AI Input: {ai_input}")
        return ai_input
    
    async def selector_button_callback(self, di, di_value, dt_secs, counter, edge):
        if self.hh_pressure_active or self.ll_tank_level_active:
            self.hh_pressure_active = False
            self.ll_tank_level_active = False
            self.dashboard_interface.clear_faults()
            return
        self.dashboard_interface.toggleSelectedPump()
        
    async def start_pump_callback(self, di, di_value, dt_secs, counter, edge):
        if not self.start_first_callback:
            self.start_first_callback = True
            return
        # self.dashboard_interface.start_pump()
        # self.dashboard_interface.updateSelectedPumpState("pumping")
        pump_number = self.dashboard_interface.getSelectedPump()
        log.info(f"Starting Pump {pump_number}")
        await self.update_pump_state_tag(pump_number, 2)
        
    async def stop_pump_callback(self, di, di_value, dt_secs, counter, edge):
        # self.dashboard_interface.stop_pump()
        # self.dashboard_interface.updateSelectedPumpState("standby")
        pump_number = self.dashboard_interface.getSelectedPump()
        log.info(f"Stopping Pump {pump_number}")
        await self.update_pump_state_tag(pump_number, 0)
        
    async def update_pump_state_tag(self, pump_number, state):
        
        if pump_number == 1:
            await self.set_tag("StateWrite", state, self.config.pump_1.value)
        elif pump_number == 2:
            await self.set_tag("StateWrite", state, self.config.pump_2.value)
        

    async def update_dashboard_data(self):
        """Update dashboard with data from various sources."""
        # try:
            # Get pump control data from simulators
        target_rate = self.get_tag("TargetRate", self.config.pump_1.value) 
        flow_rate = self.get_tag("FlowRate", self.config.pump_1.value) 
        pump_state = self.get_tag("StateString", self.config.pump_1.value) 
        
        # Update pump data
        self.dashboard_interface.update_pump_data(
            target_rate=target_rate,
            flow_rate=flow_rate,
            pump_state=pump_state
        )
        
        # Get pump 2 control data from simulators
        # if len(self.config.pump_controllers.elements) > 1:
        pump2_target_rate = self.get_tag("TargetRate", self.config.pump_2.value)
        pump2_flow_rate = self.get_tag("FlowRate", self.config.pump_2.value)
        pump2_pump_state = self.get_tag("StateString", self.config.pump_2.value)
        # else:
        #     # Fallback values for pump 2 if not configured
        #     pump2_target_rate = "-"
        #     pump2_flow_rate = "-"
        #     pump2_pump_state = "-"
        
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
            panel_voltage_values = []
            battery_ah_values = []
            
            # Collect data from all solar controllers
            for solar_controller in self.config.solar_controllers.elements:
                r = self.get_tag("b_voltage", solar_controller.value)
                if r is not None:
                    battery_voltages.append(float(r))
                    
                r = self.get_tag("b_percent", solar_controller.value)
                if r is not None:
                    battery_percentages.append(float(r))
                r = self.get_tag("panel_voltage", solar_controller.value)
                
                if r is not None:
                    panel_voltage_values.append(float(r))
                r = self.get_tag("remaining_ah", solar_controller.value)
                if r is not None:
                    battery_ah_values.append(float(r))
            
            # Aggregate data: average voltages/percentages, sum battery_ah
            if battery_voltages:
                battery_voltage = sum(battery_voltages) / len(battery_voltages)
            else:
                battery_voltage = 0.0
            if battery_percentages:
                battery_percentage = sum(battery_percentages) / len(battery_percentages)
            else:
                battery_percentage = 0.0
            if panel_voltage_values:
                panel_voltage = sum(panel_voltage_values) / len(panel_voltage_values)
                if panel_voltage < 0:
                    panel_voltage = 0.0
            else:
                panel_voltage = 0.0
            
            if battery_ah_values:
                battery_ah = sum(battery_ah_values) 
            else:
                battery_ah = 0.0
            
        # else:
        #     # Fallback values if no solar controllers configured
        #     battery_voltage = 24.5
        #     battery_percentage = 78.0
        #     panel_power = 150.0
        #     battery_ah = 120.0
        
        # Update solar data
        self.dashboard_interface.update_solar_data(
            battery_voltage=battery_voltage,
            battery_percentage=battery_percentage,
            array_voltage=panel_voltage,
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