# SMU module Testing
from SMU_drivers.Keysight_SMU import SMU
# import numpy as np

if __name__ == '__main__':
    smu = SMU(None, 1, 'inst')
    print(smu.set_pulse_config(1))