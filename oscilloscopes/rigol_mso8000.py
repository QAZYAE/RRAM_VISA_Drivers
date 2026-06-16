"""
A driver for Rigol MSO8000 Series Digital Oscilloscope
"""
from RRAM_VISA_Drivers.core import VISA_instrument
from typing import Union
import pyvisa
import numpy as np



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
        IDN_response = 'RIGOL TECHNOLOGIES,MSO8'
        super().__init__(resource, IDN_response=IDN_response, instrument_name=instrument_name)
    

    def fetch_waveform(self, channel: int = 1, form: str = 'ascii', mode: str = 'norm', apply: bool = True):

        """ Fetch data from oscilloscope screen

        Args:
        channel (str, optional): Channel from which the waveform will be read: '1' | '2' | '3' | '4'.
        form (str, optional): {WORD|BYTE|ASCii}
        mode (str, optional): {NORMal|MAXimum|RAW}
        apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
            the command is appended to the `command_queue` and can be sent with `.send_queue()` method.

        Returns:
            data (lst): raw data from the oscilloscope | error if an error occurred.
        """

        if str(channel) not in ['1', '2', '3', '4']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        self.command(f'wav:sour chan{channel}', apply=apply)
        self.command(f'wav:mode {mode}', apply=apply)
        self.command(f'wav:form {form}', apply=apply)

        return self.query('wav:data?')


    def parse_waveform(self, rawdata, xorigin: bool = False):


        """ Parse fetched data in ASCII

        Args:
        rawdata (lst): raw data from the oscilloscope in ASCII format
        channel (str, optional): Channel from which the waveform will be read: '1' | '2' | '3' | '4'.
        apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
            the command is appended to the `command_queue` and can be sent with `.send_queue()` method.

        Returns:
            time (numpy array): data in the X direction
            data (lst): waveform from the oscilloscope | error if an error occurred.
        """
                
        n_bytes = int(rawdata[2:11])
        data = (rawdata[11:n_bytes+11]).split(',')
        data = [float(i) for i in data[:-1]]
        delta_t = self.query('wav:xinc?')
        if xorigin:
            t0 = float(self.query('wav:xor?'))
        else:
            t0 = 0
        time = np.arrange(t0, len(data), delta_t)

        return time, data

    def auto_scale(self, apply: bool = False):

        self.command('auto', apply=apply)

        return
    
    def run(self, apply: bool = False):

        self.command('run', apply=apply)

        return
    
    def stop(self, apply: bool = False):

        self.command('stop', apply=apply)

        return
    
    def single(self, apply: bool = False):

        self.command('sing', apply=apply)

        return
    
    def measure_amplitude(self, channel: int = 1, apply: bool = False):

        self.command(f'meas:ams channel{channel}', apply=apply)

        return self.query(f'meas:item vpp,chan{channel}')