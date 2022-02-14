import tomato.drivers
import time


pl = [
    {
        "name": "OCV", 
        "time": 5, 
        "record_every_dt": 1
    },
    {
        "name": "CPLIMIT", 
        "current": [-0.004, 0.005],
        "time": 600, 
        "is_delta": False,
        "record_every_dt": 10,
        "record_every_dE": 0.01,
        "I_range": "10 mA",
        "limit_voltage_max": 4.1,
        "limit_voltage_min": 3.0,
        "n_cycles": 10
    }
]

address = "192.109.209.6"
channel = 1
dllpath = "C:\\EC-Lab Development Package\\EC-Lab Development Package\\"
capacity = 45e-3

print(tomato.drivers.biologic.get_status(address, channel, dllpath))
print(tomato.drivers.biologic.start_job(address, channel, dllpath, pl, capacity))
for i in range(100):
    print(f"cycle number {i}/100")
    print(tomato.drivers.biologic.get_status(address, channel, dllpath))
    print(tomato.drivers.biologic.get_data(address, channel, dllpath))
    time.sleep(10)
