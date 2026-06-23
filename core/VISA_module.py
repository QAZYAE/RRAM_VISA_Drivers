"""
VISA module class
"""
import pyvisa
from typing import Union
import logging



class VISA_module:
    """General class for VISA instruments or modules. Write and query methods are implemented
    
    Attributes:
        resource (pyvisa.Resource): Instrument resource.
        sim (bool): True if in Simulation mode.
        module_name (str): Module name for responses.
        resp (str): Beginning of the response string.
        scpi_logger (logging.Logger | None): Logger for SCPI commands.

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
        module_name: str = 'Module',
        scpi_logger: Union[logging.Logger, None] = None
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
        self.scpi_logger = scpi_logger
        if resource is None:
            self.sim = True
            self.resp = f'Simulation: {module_name}:'
        else:
            self.sim = False
            self.resp = f'{module_name}:'
            
            
    def log_write(self, command: str) -> None:
        """Log the SCPI command sent via .write().

        Args:
            command (str): SCPI command
        """
        if self.scpi_logger is not None:
            self.scpi_logger.info(f'{self.resp}: WRITE: {command}')
            
            
    def write(self, commands: Union[list, str], stop_exception: bool = True) -> list:
        """Send sequence of SCPI commands to the instrument. Returns exception if an it occurs.

        Args:
            commands (list | str): List of SCPI commands (strings).
            stop_exception (bool, optional): If True, stops sending commands when an exception occurs. 
                Defaults to False.
            
        Returns:
            commands (list): List of executed commands or Visa Errors.
        """
        if type(commands) is not list:
            commands = [commands]
        if self.sim:
            return ['Simulation mode. Commands sent:'] + commands
        executed = []
        for command in commands:
            try:
                self.resource.write(command)
                self.log_write(command)
                executed.append(command)
            except Exception as e:
                executed.append(f'VISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {e}')
                self.log_write(f'ERROR: COMMAND {command}\n{type(e).__name__}: {e}')
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
                an error occurred.'  
        """
        if self.sim:
            return f'{self.resp} {normal_response}'
        try:
            self.resource.write(command)
            self.log_write(f'{command}; PURPOSE: {normal_response}')
            return f'{self.resp} {normal_response}'
        except Exception as e:
            # TODO logger
            return f'ERROR: {self.resp}\n\tVISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {e}'
    
    
    def query(self, command: str) -> str:
        """Send SCPI command and read response. Returns exception if an exception occurs.

        Args:
            command (str): SCPI command.

        Returns:
            query_response (str): Instrument response. Returns Visa Error if an exception occurred.
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
                response is sim_resp is in simulation mode, exception if an exception occurred
                    and query_response if the query was successful.
        """
        if self.sim:
            return False, f'{self.resp} {sim_resp}'
        try:
            response = self.resource.query(command)
            return True, response
        except Exception as e:
            return False, f'ERROR: {self.resp}\n\tVISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {e}'