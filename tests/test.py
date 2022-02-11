import tomato.drivers
import time


pl = [
    {
        "name": "OCV", 
        "time": 60, 
        "record_every_dt": 10
    },
    {
        "name": "CPLIMIT", 
        "current": 0.001,
        "time": 600, 
        "is_delta": False,
        "record_every_dt": 5,
        "record_every_dE": 0.01,
        "I_range": 8,
        "limit_voltage_max": 4.0
    }
]

address = "192.109.209.6"
channel = 1
dllpath = "C:\\EC-Lab Development Package\\EC-Lab Development Package\\"

print(tomato.drivers.biologic.get_status(address, channel, dllpath))
tomato.drivers.biologic.start_job(address, channel, dllpath, pl)
time.sleep(10)
print(tomato.drivers.biologic.get_status(address, channel, dllpath))
print(tomato.drivers.biologic.get_data(address, channel, dllpath))
time.sleep(20)
print(tomato.drivers.biologic.get_data(address, channel, dllpath))
time.sleep(20)
print(tomato.drivers.biologic.get_data(address, channel, dllpath))
time.sleep(20)
print(tomato.drivers.biologic.get_data(address, channel, dllpath))
time.sleep(20)
print(tomato.drivers.biologic.get_data(address, channel, dllpath))