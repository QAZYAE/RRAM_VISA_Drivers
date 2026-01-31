"""
Drivers for configuring SMU's (Source-Measure Units) on Keysight B2902B
"""
import pyvisa 
from typing import Union
from VISA_utility import VISA_module


class SMU(VISA_module):
    """Handles communicating with an SMU (Source-Measure Unit) on a Keysight instrument.
    
    Attributes:
        resource (pyvisa.resource): Keysight instrument resource.
        ch (int): SMU channel on the instrument.
        inst_name (str): Instrument name for responses.
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        channel: int, 
        instrument_name: str = 'Instrument',
    ) -> None:
        """Handles communicating with an SMU (Source-Measure Unit) on a Keysight instrument.

        Args:
            resource (pyvisa.Resource | None): Keysight instrument resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            channel (int): Channel number on the instrumetn mainframe.
            instrument_name (str, optional): Instrument name for responses. Defaults to 'Instruments'.
        """
        if channel < 1 or channel > 8:
            raise RuntimeError('ERROR: wrong channel number. Allowed channel numbers are 1 through 8.')
        self.ch = channel
        self.inst_name = instrument_name
        super().__init__(resource, module_name=f'{self.inst_name}, channel {self.ch}')
        
        
    def set_output_state(self, state: str) -> None:
        """Set SMU output state

        Args:
            state (str): output state. Valid values: 1|on|0|off.
            
        Returns: 
            response (str): Command response | error if an error occured.
        """
        if state.lower() not in ['1', 'on', '0', 'off']:
            return f'ERROR: {self.resp} Invalid state. Valid values: 1|on|0|off (str).'
        return self.write_resp(f':output{self.ch} {state}', f'Output state is set to {state}')