from collections.abc import Callable
from RRAM_VISA_Drivers.core.gui_connection import check_connection_B2902B, check_connection_34980A



# List of drivers, instruments they are using and check connection functions

_driver_instruments: dict[str: dict[str: Callable]] = {
    'ITC_probe_station': {
        'B2902B (Mem,T)': check_connection_B2902B,
    },
    'ITC_1T1R_probe_station': {
        'B2902B-1 (BL,NL)': check_connection_B2902B,
        'B2902B-2 (WL,T)': check_connection_B2902B, 
    },
    'ITC_1T1R_32x8_switched': {
        'B2902B-1 (BL,NL)': check_connection_B2902B,
        'B2902B-2 (WL,T)': check_connection_B2902B, 
        '34980A (Switch)': check_connection_34980A
    }
}



def get_driver_instruments(driver_name: str) -> dict:
    """Get list of instruments names required for the driver

    Args:
        driver_name (str): Driver name.

    Returns:
        Instruments (dict): Dict: {instrument_name (str): check_connection_function(visa_address: str, visa_library_path: str)}
    """
    return _driver_instruments[driver_name]
