"""
Functions for GUI connection
"""
import pyvisa



def update_visa_instruments_list(visa_library_path: str = '') -> list:
    """Get list of connected VISA instruments.
    
    Args:
        visa_library_path (str, optional): Visa library path. Defaults to ''.

    Returns:
        instruments (list): Instrument list.
    """
    if visa_library_path == '':
        rm = pyvisa.ResourceManager()
    else:
        rm = pyvisa.ResourceManager(visa_library_path)
    resources = rm.list_resources()
    rm.close()
    return resources


def check_VISA_connection(visa_address: str, correct_resp: str, visa_library_path: str = '', beep: bool = False) -> tuple[int, str]:
    """Check connection with a VISA instrument.

    Args:
        visa_address (str): Visa Address.
        correct_resp (str): Correct response.
        visa_library_path (str, optional): Path to visa library. Defaults to ''.
        beep (bool, optional): If true, instrument beeps on checking. Defaults to False.

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
        if beep:
            inst.write('system:beeper:immediate 1000,0.2')
        rm.close()
        if resp.startswith(correct_resp):
            return 2, ' | '.join(resp[:-1].split(','))
        else:
            return 1, ' | '.join(resp[:-1].split(','))
    except Exception as e:
        return 0, f'VISA Connection Error: {e}'
    
    
def reset_instrument(visa_address: str, visa_library_path: str = '') -> tuple[bool, str]:
    """Reset a visa instrument.

    Args:
        visa_address (str): Visa Address.
        visa_library_path (str, optional): Path to visa library. Defaults to ''.

    Returns:
        (flag, response) (tuple[bool, str]): Flag is True if the instrument was reset, resonse 
            contains an error if occurred.
    """
    if visa_address == '':
        return True, ''
    try:
        if visa_library_path == '':
            rm = pyvisa.ResourceManager()
        else:
            rm = pyvisa.ResourceManager(visa_library_path)
        inst = rm.open_resource(visa_address)
        inst.write('*RST')
        rm.close()
        return True, ''
    except Exception as e:
        return False, str(e)
    
    
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
    return check_VISA_connection(visa_address, 'Keysight Technologies,B2902B', visa_library_path, beep=True)


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