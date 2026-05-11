import time
import threading

import bme680



class Settings(object):
    def __init__(self):
        self.humidity_oversample          = bme680.OS_2X
        self.pressure_oversample          = bme680.OS_4X
        self.temperature_oversample       = bme680.OS_8X
        self.filter                       = bme680.FILTER_SIZE_3
        self.gas_status                   = bme680.ENABLE_GAS_MEAS

        self.gas_heater_temperature       = 300 # 320
        self.gas_heater_duration          = 150 # 150
        self.gas_heater_profile           = 0

        self.burn_in_time                 = 90
        self.burn_in_data_number          = 60
        self.start_time                   = time.time()
        self.hum_baseline                 = 45.0
        self.hum_weighting                = 0

    def apply(self, sensor):
        sensor.set_humidity_oversample(self.humidity_oversample)
        sensor.set_pressure_oversample(self.pressure_oversample)
        sensor.set_temperature_oversample(self.temperature_oversample)
        sensor.set_filter(self.filter)
        sensor.set_gas_status(self.gas_status)

        sensor.set_gas_heater_temperature(self.gas_heater_temperature)
        sensor.set_gas_heater_duration(self.gas_heater_duration)
        sensor.select_gas_heater_profile(self.gas_heater_profile)
        return sensor


def init_env(settings):
    sensor = None
    try:
        sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
    except (RuntimeError, IOError) as e:
        try:
            sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)
        except (RuntimeError, IOError):
            return None

    if sensor is not None:
        try:
            return settings.apply(sensor)
        except Exception as e:
            print(f"[ERROR] Failed to apply settings to BME680: {e}")
            return None
    return None

def start_burn_in(bme):
    bme.burn_in_thread = threading.Thread(target=burn_in, args=(bme,), daemon=True)
    bme.burn_in_thread.start()


def burn_in(bme):
    if bme.device is None:
        print("[INFO] BME680 not connected, skipping burn-in")
        bme.burn_in_finished = True
        return
    while not bme.burn_in_finished:
        try:
            bme.Settings.start_time = time.time()
            while time.time() - bme.Settings.start_time < bme.Settings.burn_in_time:
                if bme.device.get_sensor_data() and bme.device.data.heat_stable:
                    bme.gas_resistance = bme.device.data.gas_resistance
                    bme.burn_in_data.append(bme.gas_resistance)
                    time.sleep(1)
            bme.gas_baseline = sum(bme.burn_in_data[((-1)*(bme.Settings.burn_in_data_number)):]) / float(bme.Settings.burn_in_data_number)
            print(f"[INFO] burn-in finished in {time.time() - bme.Settings.start_time} s")
            print('[INFO] Gas baseline:', bme.gas_baseline, 'Ohms')
            bme.burn_in_finished = True
        except:
            print('[ERROR] Burn-in thread died. Restarting thread...')
            time.sleep(1)


def get_temperature(bme):
    bme.temperature = bme.device.data.temperature


def get_pressure(bme):
    bme.pressure = bme.device.data.pressure


def get_humidity(bme):
    bme.humidity = bme.device.data.humidity

def get_gas_resistance(bme):
    if bme.device.data.heat_stable and bme.gas_baseline != None:
        bme.gas_resistance = bme.device.data.gas_resistance


def get_all_data(bme):
    if bme.device is None:
        return
    if bme.device.get_sensor_data():
        get_temperature(bme)
        get_pressure(bme)
        get_humidity(bme)
        get_gas_resistance(bme)

        get_iaq(bme)


def get_iaq(bme):
    if bme.burn_in_finished and bme.device.data.heat_stable:
        gas = bme.device.data.gas_resistance
        gas_offset = bme.gas_baseline - gas

        bme.gas_resistance = gas

        hum = bme.device.data.humidity
        hum_offset = hum - bme.Settings.hum_baseline

        if hum_offset > 0:
            hum_score = (100 - bme.Settings.hum_baseline - hum_offset) / (100 - bme.Settings.hum_baseline) * bme.Settings.hum_weighting * 100
        else:
            hum_score = (bme.Settings.hum_baseline + hum_offset) / bme.Settings.hum_baseline * bme.Settings.hum_weighting * 100

        if gas_offset > 0:
            gas_score = gas / bme.gas_baseline * (100 - bme.Settings.hum_weighting * 100)
        else:
            gas_score = 100 - bme.Settings.hum_weighting * 100

        bme.air_quality_score = hum_score + gas_score
