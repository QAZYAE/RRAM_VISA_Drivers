"""
Взаимодействие с GUI MemriBoard
"""
import pyvisa
from Switch_drivers.Keysight_34980A_1T1R_32x8 import Keysight_34980A_1T1R_32x8
from SMU_drivers.Keysight_SMU import SMU



config_path = 'config/Keysight_34980A_1T1R_32x8.json'  # Путь к файлу с конфигурацией оборудования
VISA_adress = 'TCPIP0::192.168.0.103::inst0::INSTR'  # VISA-адрес
simulator = True  # Режим симуляции


# Примеры использования:


# Инициализация устройства (по нажатию кнопки "подключить" и открытию окна "кроссбар")
if simulator:
    switch_resource = None
else:
    rm = pyvisa.ResourceManager()
    switch_resource = rm.open_resource(VISA_adress)
# Для режима симуляции в качестве ресурса (switch_resource) передается None
switch = Keysight_34980A_1T1R_32x8(switch_resource, config_path=config_path)



# Проверка подключения и устройства:
switch.check_instument_connection()  # True если подключено правильное устройство



# Очистка очереди ошибок. Можно их сбрасывать в какой-нибудь лог (не обязательно)
switch.get_errors()  # Возвращает list с ошибками (ошибки - str). В режиме симуляции возвращает None. 
# Если ошибок нет, возвращает None



# Отключение всех каналов коммутатора. В идеале отправлять эту команду при закрытии MemriBoard.
switch.disconnect_all()



# Режим Standby: все ячейки отключены, но затворы транзисторов подключены к земле. 
# Этот режим должен быть включен, когда MemriBoard работает, но эксперимент не идёт.
# В него нужно переходить при завершении или остановке эксперимента. 
# При инициализации класса Keysight_34980A_1T1R_32x8 режим включается автоматически.
switch.standby()


# Подключение ячейки. Это нужно сделать один раз, когда начинается эксперимент с конкретной ячейкой памяти
switch.connect_cell(row=3, column=24)  # Ячейка wl=2,bl=23 в GUI
# ВАЖНО: адресация в коммутаторе начинается с 1, соответственно, и в драйвере она с 1. К тому же, 
# матрица транспонирована относительно GUI MemriBoard: 
# Параметр row задает номер WL/NL от 1 до 8 включительно (в GUI это столбцы от 0 до 7) 
# Параметр column задает номер BL от 1 до 32 включительно (в GUI это строки от 0 до 31)

# Методы disconnect_all(), standby() и connect_cell() возвращают строки (в т.ч. в режиме симуляции), 
# описывающие, что произошло. Их можно записывать в логи.






# SMU module Testing
if __name__ == '__main__':
    smu = SMU(None, 1, 'inst')
    print(smu.get_output_state())