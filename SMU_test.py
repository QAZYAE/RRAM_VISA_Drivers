# SMU module Testing
# from SMU_drivers.Keysight_SMU import SMU
from SMU_drivers.Keysight_B2902B import B2902B
# import numpy as np

if __name__ == '__main__':
    
    inst = B2902B(None, 'inst')
    # print(inst.beep(1, 1))
    # print(inst.configure_digital_io_trigger(1, 'input'))
    print(inst.fetch_array())