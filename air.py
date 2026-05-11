import serial
import time
import struct
import threading

latest_data = None
data_lock = threading.Lock()
restart_event = threading.Event()


def isNum(val):
    try:
        float(val)
        return True
    except ValueError:
        return False


class Settings(object):
    def __init__(self):
        self.device = None
        self.primary_uart_port = '/dev/ttyS0'
        self.secondary_uart_port = '/dev/ttyAMA0'
        self.timeout = 2
        self.baud_rate = 9600
        self.read_atmospheric = False


def connect_to_port(port, settings, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        try:
            ser = serial.Serial(
                port,
                settings.baud_rate,
                timeout=settings.timeout,
                write_timeout=settings.timeout
            )
            # Flush any garbage data that might be in the buffer
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            return ser
        except (serial.SerialException, OSError) as e:
            print(f"[ERROR] Attempt {attempt}/{max_attempts} failed to connect to {port}: {e}")
            if attempt < max_attempts:
                time.sleep(attempt * 2)  # Exponential backoff: 2, 4, 6, 8 seconds
    return None


def init_air(settings):
    ser = connect_to_port(settings.primary_uart_port, settings)
    if ser is None:
        print(f"[ERROR] Failed to connect to {settings.primary_uart_port}")
        ser = connect_to_port(settings.secondary_uart_port, settings)
        if ser is None:
            print(f"[CRITICAL] Failed to connect to {settings.secondary_uart_port}")
    if ser is None:
        print("[CRITICAL] Failed to connect to any port. Check your settings.")
    else:
        start_data_reading_thread(ser)
    return ser


def validate_frame(data):
    if len(data) != 32:
        return -1
    if not data.startswith(b'BM'):
        return -2

    frame_len = struct.unpack(">H", data[2:4])[0]
    if frame_len != 28:
        return -3

    # Verify checksum
    checksum = struct.unpack(">H", data[30:32])[0]
    calculated_checksum = sum(data[:30]) & 0xFFFF
    if checksum != calculated_checksum:
        return -4  # Bad checksum
    # 0 if valid, -1 if wrong length, -2 if wrong start bytes, -3 if wrong frame length
    return 0


def read_frame_with_retry(serial, max_attempts=100):
    # Sync to frame start
    discarded = 0
    while discarded < max_attempts:
        byte = serial.read(1)
        if not byte:
            # Timeout - no data available
            return None

        if byte == b'B':
            # Possible start of frame, read next byte
            next_byte = serial.read(1)
            if next_byte == b'M':
                # Found frame start, read remaining 30 bytes
                remaining = serial.read(30)
                if len(remaining) == 30:
                    return b'BM' + remaining
            # Not a valid start, continue searching
            discarded += 1
        else:
            discarded += 1

    return None


def read_uart_data(serial):
    global latest_data

    consecutive_errors = 0
    max_consecutive_errors = 10
    stall_timeout = 5.0  # Seconds before considering connection stalled

    while True:
        try:
            # Check if restart requested
            if restart_event.is_set():
                break

            # Try to read a complete frame
            frame = read_frame_with_retry(serial, max_attempts=200)

            if frame is None:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    print("[WARNING] Too many consecutive read failures, resetting buffer")
                    serial.reset_input_buffer()
                    consecutive_errors = 0
                continue

            # Validate the frame
            if validate_frame(frame) == 0:
                with data_lock:
                    latest_data = frame
                consecutive_errors = 0  # Reset error counter on success
            else:
                consecutive_errors += 1

        except serial.SerialException as e:
            print(f"[ERROR] Serial exception in read loop: {e}")
            consecutive_errors += 1
            if consecutive_errors >= 3:
                # Try to recover by resetting
                try:
                    serial.reset_input_buffer()
                except:
                    pass
                consecutive_errors = 0
            time.sleep(0.1)

        except Exception as e:
            print(f"[ERROR] Unexpected error in read loop: {e}")
            consecutive_errors += 1
            time.sleep(0.1)

    restart_event.clear()
    threading.Timer(5.0, restart_read_uart_data, args=(serial,)).start()


def restart_read_uart_data(serial):
    restart_event.set()


def start_data_reading_thread(serial):
    data_thread = threading.Thread(target=read_uart_data, args=(serial,))
    data_thread.daemon = True
    data_thread.start()


def get_all_data(pms):
    if pms.device is None:
        return

    global latest_data
    with data_lock:
        data = latest_data

    if data is None:
        return None

    # Validate frame
    if len(data) != 32:
        return -1
    if not data.startswith(b'BM'):
        return -2

    frame_len = struct.unpack(">H", data[2:4])[0]
    if frame_len != 28:
        return -3

    # Extract PM concentrations based on mode
    if pms.Settings.read_atmospheric:
        pm1_0 = struct.unpack(">H", data[10:12])[0]
        pm2_5 = struct.unpack(">H", data[12:14])[0]
        pm10 = struct.unpack(">H", data[14:16])[0]
    else:
        pm1_0 = struct.unpack(">H", data[4:6])[0]
        pm2_5 = struct.unpack(">H", data[6:8])[0]
        pm10 = struct.unpack(">H", data[8:10])[0]

    # Assign standard particulate matter
    pms.pm1_0 = pm1_0
    pms.pm2_5 = pm2_5
    pms.pm10 = pm10

    # Extract particle count data
    pms.p0_3 = struct.unpack(">H", data[16:18])[0]
    pms.p0_5 = struct.unpack(">H", data[18:20])[0]
    pms.p1_0 = struct.unpack(">H", data[20:22])[0]
    pms.p2_5 = struct.unpack(">H", data[22:24])[0]
    pms.p5_0 = struct.unpack(">H", data[24:26])[0]
    pms.p10 = struct.unpack(">H", data[26:28])[0]

    # Extract metadata
    pms.version = data[28]
    pms.error_code = data[29]
    pms.checksum = struct.unpack(">H", data[30:32])[0]


def calculate_aqi_us(pm2_5, pm10):
    if not isNum(pm2_5) or not isNum(pm10):
        return "-"

    pm2_5 = float(pm2_5)
    pm10 = float(pm10)

    # Breakpoints and AQI ranges
    pm25_breakpoints = [
        (0.0, 12.0), (12.1, 35.4), (35.5, 55.4),
        (55.5, 150.4), (150.5, 250.4), (250.5, 350.4), (350.5, 500.4)
    ]
    pm10_breakpoints = [
        (0.0, 54), (55, 154), (155, 254),
        (255, 354), (355, 424), (425, 504), (505, 604)
    ]
    aqi_ranges = [
        (0, 50), (51, 100), (101, 150),
        (151, 200), (201, 300), (301, 400), (401, 500)
    ]

    def calculate_individual_aqi(concentration, breakpoints):
        for i, (low, high) in enumerate(breakpoints):
            if low <= concentration <= high:
                aqi_low, aqi_high = aqi_ranges[i]
                return (concentration - low) / (high - low) * (aqi_high - aqi_low) + aqi_low
        return 0.0

    pm25_aqi = calculate_individual_aqi(pm2_5, pm25_breakpoints)
    pm10_aqi = calculate_individual_aqi(pm10, pm10_breakpoints)

    return max(int(max(pm25_aqi, pm10_aqi) ** 0.95), 0)


def calculate_aqi_eu(pm2_5, pm10):
    if not isNum(pm2_5) or not isNum(pm10):
        return "-"

    pm2_5 = float(pm2_5)
    pm10 = float(pm10)

    # European breakpoints (6 levels)
    breakpoints_pm25 = [
        (0.0, 10.0), (10.1, 20.0), (20.1, 25.0),
        (25.1, 50.0), (50.1, 75.0), (75.1, 800.0)
    ]
    breakpoints_pm10 = [
        (0.0, 20.0), (20.1, 40.0), (40.1, 50.0),
        (50.1, 100.0), (100.1, 150.0), (150.1, 1200.0)
    ]

    def calculate_individual_aqi(concentration, breakpoints):
        for i, (low, high) in enumerate(breakpoints):
            if low <= concentration <= high:
                aqi_min = (i + 1) * 1.0
                aqi_max = (i + 2) * 1.0
                aqi = ((concentration - low) / (high - low)) * (aqi_max - aqi_min) + aqi_min
                return "{:.2f}".format(aqi)
        return "6.00"

    aqi_pm25 = calculate_individual_aqi(pm2_5, breakpoints_pm25)
    aqi_pm10 = calculate_individual_aqi(pm10, breakpoints_pm10)

    return max(aqi_pm25, aqi_pm10)


def calculate_pm(p0_3, p0_5, p1_0, p2_5, p5_0, method=1):
    if not isNum(p0_3) or not isNum(p0_5) or not isNum(p1_0) or not isNum(p2_5) or not isNum(p5_0):
        return 1.0001, 1.0001

    p0_3 = float(p0_3)
    p0_5 = float(p0_5)
    p1_0 = float(p1_0)
    p2_5 = float(p2_5)
    p5_0 = float(p5_0)

    if method == 1:
        pm25 = 0.006 * p0_3 + 0.006 * p0_5 + 0.07 * p1_0 + 0.0025 * p2_5 + 0.0025 * p5_0
        pm10 = 0.006 * p0_3 + 0.006 * p0_5 + 0.1 * p1_0 + 0.05 * p2_5 + 0.05 * p5_0
    elif method == 2:
        pm25_coef = 0.01
        pm10_coef = 0.0105
        pm25 = (p0_3 + p0_5 + p1_0) * pm25_coef
        pm10 = (p0_3 + p0_5 + p1_0 + p2_5 + p5_0) * pm10_coef
    else:
        return 1.0001, 1.0001

    return pm25, pm10