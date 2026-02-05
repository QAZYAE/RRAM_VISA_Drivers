# SMU module Testing
import pyvisa
import time
from SMU_drivers.Keysight_B2902B import B2902B
import matplotlib.pyplot as plt
# import numpy as np




def main():
    # Measuring two IV curves
    rm = pyvisa.ResourceManager()
    A_res = rm.open_resource('TCPIP0::192.168.0.101::inst0::INSTR')
    A = B2902B(A_res, 'A')
    A.set_standby_zero()
    A.set_output_state('on')
    
    A.clear()
    A.SMU1.set_arm_BUS()
    A.SMU2.set_arm_BUS()
    
    n_points = 11
    time_interval=0.1  # s
    A.SMU1.set_trigger_timer(interval=time_interval, count=2*n_points)
    A.SMU2.set_trigger_timer(interval=time_interval, count=2*n_points)
    
    A.SMU1.set_sweep_voltage(stop=1, n_points=n_points)
    A.SMU2.set_sweep_voltage(stop=1, n_points=n_points)
    
    A.set_data_format('voltage,current')
    
    A.initiate()
    A.arm()
    for i in range(2 * n_points):
        time.sleep(time_interval)
        print(A.get_sense_data(latest=True))
    
    data1, data2 = A.get_sense_data()
    
    _, ax = plt.subplots()
    ax.grid(ls='-', lw=1, color='grey')
    ax.plot(data1[::2], data1[1::2]*1000, lw=2, label='SMU1')
    ax.plot(data2[::2], data2[1::2]*1000, lw=2, label='SMU2')
    ax.set_xlabel('Voltage, V')
    ax.set_ylabel('Current, mA')
    ax.legend(loc='best')
    plt.show()
    # 10k, 1k







if __name__ == '__main__':
    print(main())