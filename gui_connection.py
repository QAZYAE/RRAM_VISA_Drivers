"""
Functions for GUI connection
"""
from typing import Callable
import pyvisa



_driver_instruments: dict[str: dict[str: Callable]] = {}



def set_driver_instrumetns(driver_name: str, instruments: dict) -> None:
    """Set list of instruments names required for the driver

    Args:
        driver_name (str): Driver name.
        instruments (dict): List of instruments.
    """
    _driver_instruments[driver_name] = instruments


def get_driver_instruments(driver_name: str) -> dict:
    """Get list of instruments names required for the driver

    Args:
        driver_name (str): Driver name.

    Returns:
        Instruments (dict): List of instruments.
    """
    return _driver_instruments[driver_name]


def check_VISA_connection(visa_address: str, correct_resp: str, visa_library_path: str = '') -> tuple[int, str]:
    """Check connection with a VISA instrument.

    Args:
        visa_address (str): Visa Address.
        visa_library_path (str): Path to visa library. Defaults to ''.
        correct_resp (str): Correct response.

    Returns:
        (flag, response) (tuple[int, str]): First item is a flag: 0 if connection error, 1 if connected, 
            but the instrument is wrong, 2 if connected and the instrument is right. 
            Second item is the instrument response.
    """
    if visa_address == '':
        return 2, 'Simulation'
    try:
        if visa_library_path == '':
            rm = pyvisa.ResourceManager()
        else:
            rm = pyvisa.ResourceManager(visa_library_path)
        inst = rm.open_resource(visa_address)
        resp = inst.query('*IDN?')
        rm.close()
        if resp.startswith(correct_resp):
            return 2, ' | '.join(resp[:-1].split(','))
        else:
            return 1, ' | '.join(resp[:-1].split(','))
    except Exception as e:
        print(f'VISA Connection Error: {e}')
        return 0, "Can't connect to the instrument"
    
    
def reset_VISA_instrument(visa_address: str, visa_library_path: str = '') -> bool:
    """Reset a visa instrument.

    Args:
        visa_address (str): Visa Address.
        visa_library_path (str, optional): Path to visa library. Defaults to ''.

    Returns:
        flag (bool): True if the instrument was reset.
    """
    if visa_address == '':
        return True
    try:
        if visa_library_path == '':
            rm = pyvisa.ResourceManager()
        else:
            rm = pyvisa.ResourceManager(visa_library_path)
        inst = rm.open_resource(visa_address)
        inst.write('*RST?')
        rm.close()
        return True
    except Exception as e:
        print(f'VISA Reset Error: {e}')
        return False
    
    
def check_connection_B2902B(visa_address: str, visa_library_path: str = '') -> tuple[int, str]:
    """Check connection with Keysight B2902B.

    Args:
        visa_address (str): Visa Address.
        visa_library_path (str): Path to visa library. Defaults to ''.

    Returns:
        (flag, response) (tuple[int, str]): First item is a flag: 0 if connection error, 1 if connected, 
            but the instrument is wrong, 2 if connected and the instrument is right. 
            Second item is the instrument response.
    """
    return check_VISA_connection(visa_address, 'Keysight Technologies,B2902B', visa_library_path)


def check_connection_34980A(visa_address: str, visa_library_path: str = '') -> tuple[int, str]:
    """Check connection with Keysight B2902B.

    Args:
        visa_address (str): Visa Address.
        visa_library_path (str): Path to visa library. Defaults to ''.

    Returns:
        (flag, response) (tuple[int, str]): First item is a flag: 0 if connection error, 1 if connected, 
            but the instrument is wrong, 2 if connected and the instrument is right. 
            Second item is the instrument response.
    """
    return check_VISA_connection(visa_address, 'Agilent Technologies,34980A,', visa_library_path)