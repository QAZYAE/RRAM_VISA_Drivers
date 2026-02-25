"""
Helper classes and functions
"""

import pyvisa
from typing import Union



class VISA_module:
    """General class for VISA instruments or modules. Write and query methods are implemented
    
    Attributes:
        resource (pyvisa.Resource): Instrument resource.
        sim (bool): True if in Simulation mode.
        module_name (str): Module name for responses.
        resp (str): Beginning of the response string.

    Methods:
        write(commands, stop_exception=True): Send sequence of SCPI commands to the instrument.
        query(command): Send SCPI command and read response.
        write_resp(command, normal_response): Send an SCPI command to the instrument. 
            Return normal response or an exception.
        query_resp(command, sim_resp): Send and SCPI command and read the response. 
            Returns exception if it occurs.
        
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        module_name: str = 'Module'
    ) -> None:
        """General class for VISA instruments or modules. Write and query methods are implemented

        Args:
            resource (pyvisa.Resource | None): pyvisa resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            module_name (str, optional): Module name for responses. Defaults to 'Module'.
        """
        self.resource = resource
        self.module_name = module_name
        if resource is None:
            self.sim = True
            self.resp = f'Simulation: {module_name}:'
        else:
            self.sim = False
            self.resp = f'{module_name}:'
            
            
    def write(self, commands: Union[list, str], stop_exception: bool = True) -> list:
        """Send sequence of SCPI commands to the instrument. Returns exception if an it occurs.

        Args:
            commands (list | str): List of SCPI commands (strings).
            stop_exception (bool, optional): If True, stops sending commands when an exception occurs. 
                Defaults to False.
            
        Returns:
            commands (list): List of execuded commands or Visa Errors.
        """
        if type(commands) is not list:
            commands = [commands]
        if self.sim:
            return ['Simulation mode. Commands sent:'] + commands
        executed = []
        for command in commands:
            try:
                self.resource.write(command)
                executed.append(command)
            except Exception as e:
                executed.append(f'VISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {e}')
                if stop_exception:
                    return executed
        return executed
    
    
    def write_resp(self, command: str, normal_response: str) -> str:
        """Send an SCPI command to the instrument. Return normal response or an exception.

        Args:
            command (str): SCPI command.
            normal_response (str): Normal response, which is returned if the command was sent.

        Returns:
            response (str): normal response if the command was sent. 'ERROR: ```error``` if 
                an error occured.'  
        """
        if self.sim:
            return f'{self.resp} {normal_response}'
        try:
            self.resource.write(command)
            return f'{self.resp} {normal_response}'
        except Exception as e:
            return f'ERROR: {self.resp}\n\tVISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {e}'
    
    
    def query(self, command: str) -> str:
        """Send SCPI command and read response. Returns exception if an exception occurs.

        Args:
            command (str): SCPI command.

        Returns:
            query_response (str): Instrument response. Returns Visa Error if an exception occured.
        """
        if self.sim:
            return f'{self.resp} querying command {command}'
        try:
            response = self.resource.query(command)
            return response
        except Exception as e:
            return f'VISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {e}'
        
        
    def query_resp(self, command: str, sim_resp: str) -> tuple[bool, str]:
        """Send and SCPI command and read the response. Returns exception if it occurs.

        Args:
            command (str): SCPI command
            sim_resp (str): Response for simulation mode.

        Returns:
            executed, response (tuple[bool, str]): 
                executed is True if the query was successful.
                response is sim_resp is in simulation mode, exception if an exception occured
                    and query_respose if the query was successful.
        """
        if self.sim:
            return False, f'{self.resp} {sim_resp}'
        try:
            response = self.resource.query(command)
            return True, response
        except Exception as e:
            return False, f'ERROR: {self.resp}\n\tVISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {e}'
        
        
        
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
    
    
    def check_instument_connection(self) -> bool:
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
            errors (list | None): List of erros. Returns None if there are no errors.
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
            response (str): Error if an error occured.
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
            response (str): Error if an error occured.
        """
        if self.sim:
            return 'Simulation: Instrument was cleared.'
        try:
            self.resource.clear()
            return 'The instrument was cleared'
        except Exception as e:
            return f'ERROR:\n\tCommand: "resource.clear()"\n\tVisaIOError: {e}'
    



def twodig(number: int) -> str:
    """Makes a two digit number by adding 0 if number is one digit, also converts it to str.

    Args:
        number (int): number to convert.

    Returns:
        twodig_number (str): converted string.
    """
    if number < 1 or number > 99:
        raise RuntimeError(f'twodig function: wrong number "{number}": it must have 1 or 2 digits.')
    if 1 <= number <= 9:
        return f'0{number}'
    return str(number)