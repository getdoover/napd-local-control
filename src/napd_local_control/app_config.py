from pathlib import Path

from pydoover import config


class NapdLocalControlConfig(config.Schema):
    def __init__(self):
        self.pump_controllers = config.Array(
            "Pump Controllers",
            element=config.Application("Pump Controller", description="A pump controller application"),
            description="List of pump controller applications"
        )
        
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
