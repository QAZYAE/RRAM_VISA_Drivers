try:
    from serial import Serial
except (ModuleNotFoundError, ImportError):
    raise ModuleNotFoundError('PySerial package is not installed! Run `pip install pyserial`')
from typing import Union
        


class COM:
    """Com port class"""
    def __init__(self, port: Union[str, None] = None, braudrate: int = 9600) -> None:
        self.serial = Serial(port, braudrate=braudrate)