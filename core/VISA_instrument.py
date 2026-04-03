"""
VISA instrument class
"""
import pyvisa
from typing import Union
from RRAM_VISA_Drivers.core import VISA_module
        
        
        
class VISA_instrument(VISA_module):
    """General class for VISA instruments. Write, query factory reset and 
        identification methods are implemented

    Attributes:
        resource (pyvisa.Resource): Instrument resource.
        sim (bool): True if in Simulation mode.
        IDN_response (str): Valid IDN response for the instrument.
        instrument_name (str): Instrument name for responses.
        resp (str): Beginning of the response string.
        
    Methods:
        write(commands, stop_exception=True): Send sequence of SCPI commands to the instrument.
        query(command): Send SCPI command and read response.
        write_resp(command, normal_response): Send an SCPI command to the instrument. 
            Return normal response or an exception.
        query_resp(command, sim_resp): Send and SCPI command and read the response. 
            Returns exception if it occurs.
        IDN(): Send identification command and read the response.
        check_instrument_connection(): Check the connection and validate the instrument type.
        get_errors(): Get errors from instrument's error queue.
        factory_reset(): Perform a factory reset.
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        IDN_response: str, 
        instrument_name: str = 'Instrument'
    ) -> None:
        """General class for VISA instruments.

        Args:
            resource (pyvisa.Resource | None): pyvisa resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            IDN_response (str): Instrument response for IDN command (for validation).
        """
        self.instrument_name = instrument_name
        super().__init__(resource, instrument_name)
        self.IDN_response: str = IDN_response
        
        
    def IDN(self) -> str:
        """Send SCPI command to identify the instrument and read the response.
        
        Returns:
            response (str): Instrument response.
        """
        if self.sim:
            return 'Simulation mode'
        return self.query('*IDN?')
    
    
    def check_instrument_connection(self) -> bool:
        """Check if the instrument is connected it and validate instrument type.

        Returns:
            connected (bool): True if the instrument is connected.
        """
        if self.sim:
            return True
        response = self.IDN()
        return response.startswith(self.IDN_response)
    
    
    def get_errors(self) -> Union[list, None]:
        """Get errors from instrument's error queue.

        Returns:
            errors (list | None): List of errors. Returns None if there are no errors.
        """
        if self.sim:
            return None
        errors = []
        flag = True
        while flag:
            resp = self.query('system:error?')
            if resp.startswith('+0'):
                flag = False
            elif resp.startswith('VISA ERROR'):
                flag = False
                errors.append(resp)
            else:
                errors.append(resp)
        if len(errors) == 0:
            return None
        return errors
    
    
    def memory_reset(self) -> str:
        """Resets volatile memory of the instrument.
        
        Returns:
            response (str): Error if an error occurred.
        """
        if self.sim:
            return 'Simulation: Instrument was reset.'
        write_response = self.write('*RST')[0]
        if write_response.startswith('VISA ERROR'):
            return f'ERROR: {write_response}'
        return 'Instrument was reset.'
    

    def clear(self) -> str:
        """Clear the resource (VISA method).

        Returns:
            response (str): Error if an error occurred.
        """
        if self.sim:
            return 'Simulation: Instrument was cleared.'
        try:
            self.resource.clear()
            return 'The instrument was cleared'
        except Exception as e:
            return f'ERROR:\n\tCommand: "resource.clear()"\n\tVisaIOError: {e}'