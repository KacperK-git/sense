import os
import sys

import screen
import env
import air
import uv

import wifi

import archiver

import time
import traceback
import RPi.GPIO as GPIO
import threading
import signal


def sigterm_handler(signal, frame):
    screen.lcd_clear(lcd)
    lcd.Display.module_exit()
    sys.exit(0)


class LoadingIcon:
    def __init__(self):
        self.status_tab = ['/', '-', '\\', '|']
        # self.status_tab = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖']
        self.status_number = 0

    def update(self):
        status = self.status_tab[self.status_number]
        self.status_number += 1
        if self.status_number > len(self.status_tab) - 1:
            self.status_number = 0
        return status


class Data:
    class Bme:
        def __init__(self):
            self.temperature = '-'
            self.temperature_raw = None
            self.humidity = '-'
            self.humidity_raw = None
            self.pressure = '-'
            self.pressure_raw = None
            self.gas_resistance = 'burn-in'
            self.air_quality_score = 'burn-in'

    class Pms:
        def __init__(self):
            self.pm1_0 = '-'
            self.pm2_5 = '-'
            self.pm10 = '-'
            self.p0_3 = '-'
            self.p0_5 = '-'
            self.p1_0 = '-'
            self.p2_5 = '-'
            self.p5_0 = '-'
            self.p10 = '-'

            self.pm1_0_raw = None
            self.pm2_5_raw = None
            self.pm10_raw = None
            self.p0_3_raw = None
            self.p0_5_raw = None
            self.p1_0_raw = None
            self.p2_5_raw = None
            self.p5_0_raw = None
            self.p10_raw = None

    class Uv:
        def __init__(self):
            self.uvs = '-'
            self.als = '-'

            self.uvs_raw = None
            self.als_raw = None

    class Wifi:
        def __init__(self):
            self.network_list = []

    def __init__(self):
        self.loading_icon = LoadingIcon()
        self.loading_status = self.loading_icon.update()
        self.bme_data = self.Bme()
        self.pms_data = self.Pms()
        self.uv_data = self.Uv()
        self.wifi_data = self.Wifi()

    def unpack_Bme(self, obj):
        if obj.temperature is not None:
            self.bme_data.temperature_raw = obj.temperature
            self.bme_data.temperature = str(
                round(obj.temperature, 1)) + "°C"
        if obj.humidity is not None:
            self.bme_data.humidity_raw = obj.humidity
            self.bme_data.humidity = str(
                int(obj.humidity)) + "%"
        if obj.pressure is not None:
            self.bme_data.pressure_raw = obj.pressure
            self.bme_data.pressure = str(int(round(float(obj.pressure),
                                                   0))) + "hPa"
        if obj.gas_resistance != None:
            # print(f"[ENV] gas_resistance: {obj.gas_resistance} Ohm")
            kohms = int(float(obj.gas_resistance) / 1000)
            if kohms == 12887:
                self.bme_data.gas_resistance = "const"
            else:
                self.bme_data.gas_resistance = str(kohms) + "kΩ"
        else:
            self.bme_data.gas_resistance = self.loading_status
        if obj.air_quality_score != None:
            self.bme_data.air_quality_score = "{:.0f}%".format(float(obj.air_quality_score))
        else:
            self.bme_data.air_quality_score = self.loading_status


    def unpack_Pms(self, obj):
        if obj.pm1_0 != None:
            self.pms_data.pm1_0 = str(obj.pm1_0)
        if obj.pm2_5 != None:
            self.pms_data.pm2_5 = str(obj.pm2_5)
        if obj.pm10 != None:
            self.pms_data.pm10 = str(obj.pm10)

        if obj.p0_3 != None:
            self.pms_data.p0_3 = str(obj.p0_3)
        if obj.p0_5 != None:
            self.pms_data.p0_5 = str(obj.p0_5)
        if obj.p1_0 != None:
            self.pms_data.p1_0 = str(obj.p1_0)
        if obj.p2_5 != None:
            self.pms_data.p2_5 = str(obj.p2_5)
        if obj.p5_0 != None:
            self.pms_data.p5_0 = str(obj.p5_0)
        if obj.p10 != None:
            self.pms_data.p10 = str(obj.p10)

    def unpack_Uv(self, obj):
        if obj.uvs != None:
            self.uv_data.uvs = str(obj.uvs)
        if obj.als != None:
            if str(obj.als) == "1048575" or str(obj.als) == "262143":
                self.uv_data.als = "OverLoad"
            else:
                self.uv_data.als = str(obj.als)

    def unpack_Wifi(self, obj):
        if obj.network_list != [] and obj.network_list != self.wifi_data.network_list:
            self.wifi_data.network_list = obj.network_list

    def unpack_all(self, bme, pms, bcm, wlan):
        self.unpack_Bme(bme)
        self.unpack_Pms(pms)
        self.unpack_Uv(bcm)
        self.unpack_Wifi(wlan)
        self.loading_status = self.loading_icon.update()

    def sanity_check(self):
        if self.bme_data.temperature == '-':
            print("[WARNING] No sensor data from the ENV sensor")
        if self.pms_data.pm2_5 == '-':
            print("[WARNING] No sensor data from the PMS sensor")



class Screen_Obj(object):
    def __init__(self):
        self.Settings              = screen.Settings()

        self.DefaultImage          = screen.create_image()

        self.Display               = screen.init_screen(self.Settings)
        self.Image                 = screen.create_image()
        self.Draw                  = screen.derive_draw(self.Image)

        self.current_menu          = 0
        self.menu_size             = 4

        self.vertical_pos          = 0

    def reset_frame(self):
        self.Image = self.DefaultImage.copy()
        self.Draw = screen.derive_draw(self.Image)


class Env_Obj(object):
    def __init__(self):
        self.Settings = env.Settings()
        self.device = env.init_env(self.Settings)

        self.connected = self.device is not None

        self.burn_in_finished = False
        self.burn_in_data = []
        self.gas_baseline = None

        self.temperature = None
        self.humidity = None
        self.pressure = None
        self.gas_resistance = None
        self.air_quality_score = None


class Air_Obj(object):
    def __init__(self):
        self.Settings               = air.Settings()
        self.device                 = air.init_air(self.Settings)

        self.pm1_0                  = None
        self.pm2_5                  = None
        self.pm10                   = None

        self.p0_3                   = None
        self.p0_5                   = None
        self.p1_0                   = None
        self.p2_5                   = None
        self.p5_0                   = None
        self.p10                    = None

        self.version                = None
        self.error_code             = None
        self.checksum               = None

        self.connected              = self.device is not None


class Uv_Obj(object):
    def __init__(self):
        self.Settings               = uv.Settings()
        self.device                 = uv.init_uv(self.Settings)

        self.uvs = None
        self.als = None

        self.connected = self.device is not None


class Wifi_Obj(object):
    class Network:
        def __init__(self, name, frequency, quality, signal_level, mac_address, channel):
            self.name = name
            self.frequency = frequency
            self.quality = quality
            self.signal_level = signal_level
            self.mac_address = mac_address
            self.channel = channel

        def __eq__(self, other):
            if isinstance(other, Wifi_Obj.Network):
                return self.mac_address == other.mac_address

        def __hash__(self):
            return hash(self.mac_address)

    def __init__(self):
        self.Settings                   = wifi.Settings()
        self.first_scan_started         = False
        self.scan_in_progress           = False
        self.network_list               = []
        self.visible_network_list       = []

    def scan_status_symbol(self):
        if self.scan_in_progress:
            return "[X]"
        else:
            return "[  ]"


BUTTON_RIGHT = 26
BUTTON_LEFT = 12

BUTTON_OK = 20

BUTTON_UP = 21
BUTTON_DOWN = 16


class ButtonHandler:
    def __init__(self, lcd, bme, wlan):
        self.lcd = lcd
        self.bme = bme
        self.wlan = wlan

        self.lock = threading.Lock()
        self.sleep_event = threading.Event()
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BUTTON_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.setup(BUTTON_OK, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.setup(BUTTON_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BUTTON_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


        GPIO.add_event_detect(BUTTON_RIGHT, GPIO.FALLING, callback=self.BUTTON_RIGHT_callback, bouncetime=200)
        GPIO.add_event_detect(BUTTON_LEFT, GPIO.FALLING, callback=self.BUTTON_LEFT_callback, bouncetime=200)

        GPIO.add_event_detect(BUTTON_OK, GPIO.FALLING, callback=self.BUTTON_OK_callback, bouncetime=200)

        GPIO.add_event_detect(BUTTON_UP, GPIO.FALLING, callback=self.BUTTON_UP_callback, bouncetime=200)
        GPIO.add_event_detect(BUTTON_DOWN, GPIO.FALLING, callback=self.BUTTON_DOWN_callback, bouncetime=200)

    def update_screen(self, bme, pms, bcm, wlan):
        if self.lock.acquire(blocking=False):
            try:
                data.unpack_all(bme, pms, bcm, wlan)
                if self.lcd.current_menu == 0:
                    txt = [f'TMP:{data.bme_data.temperature}',
                           f'RH:{data.bme_data.humidity}',
                           f'PRS:{data.bme_data.pressure}',
                           f'UVS:{data.uv_data.uvs}',
                           f'ALS:{data.uv_data.als}',
                           f'IAQ:{data.bme_data.air_quality_score}',
                           f'PM2.5:{data.pms_data.pm2_5}',
                           f'PM10:{data.pms_data.pm10}',
                           f'AQI(US):{air.calculate_aqi_us(data.pms_data.pm2_5, data.pms_data.pm10)}',
                           f'AQI(EU):{air.calculate_aqi_eu(data.pms_data.pm2_5, data.pms_data.pm10)}', ]
                elif self.lcd.current_menu == 1:
                    txt = [f'PM1.0:{data.pms_data.pm1_0}',
                           f'PM2.5:{data.pms_data.pm2_5}',
                           f'PM10:{data.pms_data.pm10}',
                           f'>0.3:{data.pms_data.p0_3}',
                           f'>0.5:{data.pms_data.p0_5}',
                           f'>1.0:{data.pms_data.p1_0}',
                           f'>2.5:{data.pms_data.p2_5}',
                           f'>5.0:{data.pms_data.p5_0}',
                           f'>10.0:{data.pms_data.p10}',
                           f'GRE:{data.bme_data.gas_resistance}']
                elif self.lcd.current_menu == 2:
                    txt = [f'Scan WiFi:{wlan.scan_status_symbol()}']
                    for network in wlan.visible_network_list:
                        name = network.name[0:11]
                        txt.append(f'{name}:')
                else:
                    txt = [':Restart SENSE',
                           ':Shutdown OS',
                           ':Reboot OS']

                screen.lcd_write(self.lcd, txt)
            except AttributeError as e:
                print(f"[ERROR] Screen update - missing attribute: {e}")
                import traceback
                traceback.print_exc()
            except Exception as e:
                print(f"[ERROR] Screen update failed: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.lock.release()

    # Call this method to interrupt the sleep
    def interrupt_sleep(self):
        if self.bme.burn_in_finished or True:  # Only interrupt if burn in period has been finished
            self.sleep_event.set()

    def BUTTON_RIGHT_callback(self, channel):
        self.lcd.current_menu = (self.lcd.current_menu + 1) % self.lcd.menu_size
        self.interrupt_sleep()  # Interrupt the sleep when the button is pressed

    def BUTTON_LEFT_callback(self, channel):
        self.lcd.current_menu = (self.lcd.current_menu - 1) % self.lcd.menu_size
        self.interrupt_sleep()  # Interrupt the sleep when the button is pressed

    def BUTTON_OK_callback(self, channel):
        if self.lcd.current_menu == 2:
            if self.lcd.vertical_pos == 0:
                if not self.wlan.scan_in_progress:
                    self.wlan.scan_in_progress = True
                    thread = threading.Thread(target=wifi.scan_wifi, args=(self.wlan,))
                    thread.start()
                    thread.join()

        elif self.lcd.current_menu == 3:
            if self.lcd.vertical_pos in [0, 1, 2]:
                try:
                    screen.lcd_clear(lcd)
                    lcd.Display.module_exit()
                except:
                    pass
                finally:
                    if self.lcd.vertical_pos == 0:
                        exit(123)
                    elif self.lcd.vertical_pos == 1:
                        os.system("sudo shutdown now")
                    elif self.lcd.vertical_pos == 2:
                        os.system("sudo reboot")
        self.interrupt_sleep()  # Interrupt the sleep when the button is pressed

    def BUTTON_UP_callback(self, channel):
        if self.lcd.current_menu == 2:
            self.lcd.vertical_pos = (self.lcd.vertical_pos - 1) % (
                    len(self.wlan.visible_network_list) + 1)
        elif self.lcd.current_menu == 3:
            self.lcd.vertical_pos = (self.lcd.vertical_pos - 1) % 3
        self.interrupt_sleep()

    def BUTTON_DOWN_callback(self, channel):
        if self.lcd.current_menu == 2:
            self.lcd.vertical_pos = (self.lcd.vertical_pos + 1) % (
                    len(self.wlan.visible_network_list) + 1)
        elif self.lcd.current_menu == 3:
            self.lcd.vertical_pos = (self.lcd.vertical_pos + 1) % 3
        self.interrupt_sleep()


def compile_data(bme, pms, bcm):
    if bme.connected:
        env.get_all_data(bme)
    if pms.connected:
        air.get_all_data(pms)
    if bcm.connected:
        uv.get_all_data(bcm)


data = Data()

global lcd

lcd = Screen_Obj()

signal.signal(signal.SIGTERM, sigterm_handler)

def main(output=True):

    bme = Env_Obj()

    if bme.connected:
        env.start_burn_in(bme)

    pms = Air_Obj()

    bcm = Uv_Obj()

    wlan = Wifi_Obj()

    buttons = ButtonHandler(lcd, bme, wlan)

    refresh_interval = 1

    i = 0
    while True:
        start = time.time()
        if lcd.current_menu in [0, 1]:
            compile_data(bme, pms, bcm)
        buttons.update_screen(bme, pms, bcm, wlan)
        # print(f"[INFO] Updating screen took {(time.time() - st):.4f}")
        processing_time = time.time() - start
        if output:
            # print(f"[{i}] [P]\t{processing_time:.4f}")
            print(f'{data.pms_data.pm1_0}\t'
                  f'{data.pms_data.pm2_5}\t'
                  f'{data.pms_data.pm10}\t'
                  f'{data.pms_data.p0_3}\t'
                  f'{data.pms_data.p0_5}\t'
                  f'{data.pms_data.p1_0}\t'
                  f'{data.pms_data.p2_5}\t'
                  f'{data.pms_data.p5_0}\t'
                  f'{data.pms_data.p10}\t'
                  f'{data.bme_data.air_quality_score}')
        if processing_time < refresh_interval:
            sleep_time = refresh_interval - processing_time
            buttons.sleep_event.wait(sleep_time)
        i += 1
        if i == 10:
            data.sanity_check()
        elif i == 120:
            archiver.save_data(data)
        elif i % 900 == 0:
            archiver.save_data(data)
        if i % 60 == 0:
            archiver.update_current(data)
        buttons.sleep_event.clear()


if __name__ == '__main__':
    try:
        output = True
        args = sys.argv
        if "-s" in args or "-silent" in args or "silent" in args:
            output = False
        main(output)
    except KeyboardInterrupt:
        screen.lcd_clear(lcd)
        lcd.Display.module_exit()
    except Exception as e:
        with open('error.log', 'w', encoding='utf-8') as error_log:
            error_log.write(f"{e}\n\n{traceback.format_exc()}")
        print(traceback.format_exc())
        screen.lcd_clear(lcd)
        lcd.Display.module_exit()
    finally:
        GPIO.cleanup()