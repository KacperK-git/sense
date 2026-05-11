import time
import subprocess
import re


class Settings(object):
    def __init__(self):
        self.interface            = 'wlan0'
        self.scan_command         = ["iwlist", self.interface, "scan"]
        self.blacklist            = []
        self.scan_duration        = 12


def scan_wifi(wlan):
    print("Starting wifi scan...")

    cell_re = re.compile(r'Cell \d+ - ')
    name_re = re.compile(r'ESSID:"(.*)"')
    freq_re = re.compile(r'Frequency:(\d+.\d+ GHz)')
    quality_re = re.compile(r'Quality=(\d+)/(\d+)')
    signal_re = re.compile(r'Signal level=(-?\d+ dBm)')
    mac_address_re = re.compile(r'Address: ((?:[0-9a-fA-F]:?){12})')
    channel_re = re.compile(r'Channel:(\d+)')

    start_time = time.time()

    while True:
        process = subprocess.Popen(wlan.Settings.scan_command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        stdout = stdout.decode()

        cells = cell_re.split(stdout)[1:]

        for cell in cells:
            try:
                name_match = name_re.search(cell)
                if name_match and name_match.group(1).strip():
                    name = name_match.group(1)
                else:
                    name = "<hidden>"
                if name in wlan.Settings.blacklist:
                    continue

                frequency = freq_re.search(cell).group(1)

                quality_search = quality_re.search(cell)
                quality = int(
                    int(quality_search.group(1)) / int(quality_search.group(2)) * 100) if quality_search else None

                signal_level = signal_re.search(cell).group(1)
                mac_address = mac_address_re.search(cell).group(1)
                channel = channel_re.search(cell).group(1)

                network = wlan.Network(name, frequency, quality, signal_level, mac_address, channel)

                if network in wlan.network_list:
                    existing = wlan.network_list[wlan.network_list.index(network)]
                    if existing.quality < network.quality:
                        wlan.network_list[wlan.network_list.index(network)] = network
                else:
                    wlan.network_list.append(network)
            except Exception as e:
                print(f"[WiFi Scan] Skipping malformed cell: {e}")
                continue

        if time.time() - start_time > wlan.Settings.scan_duration:
            break

    # Show up to 7 strongest (by order of discovery, not sorted here)
    wlan.visible_network_list = wlan.network_list[0:7]
    wlan.scan_in_progress = False
    wlan.first_scan_started = True

    return wlan