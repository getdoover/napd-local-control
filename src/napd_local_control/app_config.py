from pathlib import Path

from pydoover import config


class NapdLocalControlConfig(config.Schema):
    def __init__(self):
        
        self.pump_1 = config.Application("Pump 1", description="The pump 1 application")
        self.pump_2 = config.Application("Pump 2", description="The pump 2 application")
        
        self.selector_pin = config.Integer("Selector Pin", description="The selector pin")
        self.start_pump_pin = config.Integer("Start Pump Pin", description="The start pump (ai) pin")
        self.stop_pump_pin = config.Integer("Stop Pump Pin", description="The stop pump pin")
        
        self.potentiometer_pin = config.Integer("Potentiometer Pin", description="The potentiometer (ai) pin")
        
        self.pump_1_start_LED_pin = self.config.Integer("Pump 1 Start LED Pin", description="The pump 1 start LED pin")
        self.pump_1_fault_LED_pin = self.config.Integer("Pump 1 Stop LED Pin", description="The pump 1 stop LED pin")
        
        self.pump_2_start_LED_pin = self.config.Integer("Pump 2 Start LED Pin", description="The pump 2 start LED pin")
        self.pump_2_fault_LED_pin = self.config.Integer("Pump 2 Stop LED Pin", description="The pump 2 stop LED pin")
        
        self.solar_controllers = config.Array(
            "Solar Controllers", 
            element=config.Application("Solar Controller", description="A solar controller application"),
            description="List of solar controller applications"
        )
        
        self.flow_sensor_app = config.Application("Flow Sensor App", description="A flow sensor application")
        
        self.pressure_sensor_app = config.Application("Pressure Sensor App", description="A pressure sensor application")
            
        self.tank_level_app = config.Application("Tank Level App", description="The tank level application")

def export():
    NapdLocalControlConfig().export(Path(__file__).parents[2] / "doover_config.json", "napd_local_control")

if __name__ == "__main__":
    export()
