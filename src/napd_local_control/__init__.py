from pydoover.docker import run_app

from .application import NapdLocalControlApplication
from .app_config import NapdLocalControlConfig

def main():
    """
    Run the application.
    """
    run_app(NapdLocalControlApplication(config=NapdLocalControlConfig()))
