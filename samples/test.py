import tomato.drivers
import time


pl = [
    {
        "name": "open_circuit_voltage", 
        "time": 5, 
        "I_range": "1 mA",
        "E_range": "5 V",
        "record_every_dt": 1
    },
    {
        "name": "constant_current", 
        "current": ["C/10", "D/5"],
        "time": 11, 
        "is_delta": False,
        "record_every_dt": 1,
        "record_every_dE": 0.01,
        "I_range": "100 mA",
        "E_range": "10 V",
        "limit_voltage_max": 4.1,
        "limit_voltage_min": 3.0,
        "n_cycles": 2
    },
    {
        "name": "constant_current",
        "current": "C/8",
        "time": 100,
        "is_delta": False,
        "record_every_dt": 2,
        "I_range": "10 mA",
        "E_range": "5 V",
        "limit_voltage_max": 4.1
    },
    {
        "name": "constant_voltage",
        "voltage": 4.1,
        "time": 180,
        "is_delta": False,
        "record_every_dt": 2,
        "I_range": "10 mA",
        "E_range": "5 V",
        "limit_current_min": "C/10"
    },
    {
        "name": "constant_current",
        "current": "D/2",
        "time": 100,
        "is_delta": False,
        "record_every_dt": 2,
        "I_range": "100 mA",
        "E_range": "10 V",
        "limit_voltage_min": 3.9
    },
    {
        "name": "loop",
        "n_gotos": 5,
        "goto": 2
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
    time.sleep(10)
    ts, blob = tomato.drivers.biologic.get_data(address, channel, dllpath)
    data = blob.pop("data")
    print((ts, blob))
    try:
        print(data[0])
        print(data[-1])
    except IndexError as e:
        print(e)
    if blob["status"] == "STOP" and blob["technique_name"] == "NONE":
        break
