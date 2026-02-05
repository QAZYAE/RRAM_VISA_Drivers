# SMU module Testing
import pyvisa
import time
from SMU_drivers.Keysight_SMU import SMU
from SMU_drivers.Keysight_B2902B import B2902B
# import numpy as np




def main():
    rm = pyvisa.ResourceManager()
    A_res = rm.open_resource('TCPIP0::WindowsCE::inst0::INSTR')
    A = B2902B(A_res, 'A')
    A.set_standby_zero()
    A.set_output_state('on')

    s1 = A.SMU1

    s1.set_arm_BUS()
    s1.set_trigger_BUS(11)
    print(s1.get_trigger_config())
    s1.set_sweep_voltage(1, 11)
    s1.initiate()
    s1.arm()
    for i in range(1):
        s1.trigger()
        time.sleep(1e-4)
    # print(s1.get_sense_data())
    s1.resource.clear()
    # return A.fetch_array('current')







if __name__ == '__main__':
    print(main())