"""
A driver for Rigol MSO8000 Series Digital Oscilloscope
"""
from RRAM_VISA_Drivers.core import VISA_instrument
from typing import Union
import pyvisa



class Rigol_MSO8000(VISA_instrument):
    """A driver for Rigol MSO8000 Series Digital Oscilloscope.
    
    Attributes:
        command_queue (list): Command queue for the instrument.
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        instrument_name: str = 'MSO8000'
    ) -> None:
        """Handles communicating with Rigol MSO8000 using pyvisa.

        Args:
            resource (pyvisa.Resource | None): Instrument's resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            instrument_name (str, optional): Instrument name for responses. Defaults to 'MSO8000'.
        """
        IDN_response = 'Rigol Technologies,MSO8'
        super().__init__(resource, IDN_response=IDN_response, instrument_name=instrument_name)