import json
import sqlite3
from datetime import datetime
import air

def try_int(value):
    try:
        int(value)
        return int(value)
    except ValueError:
        return value

def try_float(value):
    try:
        float(value)
        return float(value)
    except ValueError:
        return value

# Initialize the SQLite database and create tables
def initialize_database():
    conn = sqlite3.connect("./data_archive/data.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bme_data (
            timestamp TEXT PRIMARY KEY,
            temperature REAL,
            humidity REAL,
            pressure REAL,
            gas_resistance INTEGER,
            air_quality_score INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pms_data (
            timestamp TEXT PRIMARY KEY,
            pm1_0 INTEGER,
            pm2_5 INTEGER,
            pm10 INTEGER,
            p0_3 INTEGER,
            p0_5 INTEGER,
            p1_0 INTEGER,
            p2_5 INTEGER,
            p5_0 INTEGER,
            p10 INTEGER,
            aqi_us INTEGER,
            aqi_eu REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uv_data (
            timestamp TEXT PRIMARY KEY,
            uvs INTEGER,
            als INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wifi_data (
            timestamp TEXT,
            name TEXT,
            frequency INTEGER,
            quality INTEGER,
            signal_level INTEGER,
            mac_address TEXT,
            channel INTEGER,
            PRIMARY KEY (timestamp, mac_address)
        )
    ''')

    conn.commit()
    conn.close()

# Write JSON file for compatibility
def write_current(data):
    with open("./data_archive/current.json", "w") as f:
        f.write(json.dumps(data))

def write_data_file(data):
    with open("./data_archive/data.json", "a") as f:
        f.write(json.dumps(data) + "\n")

# Save data in both JSON and SQLite formats
def save_data(data_obj, return_data=False, write_data=True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Prepare data for JSON
    network_list_serializable = []
    for network in data_obj.wifi_data.network_list:
        network_serializable = {
            "name": network.name,
            "frequency": network.frequency,
            "quality": network.quality,
            "signal_level": network.signal_level,
            "mac_address": network.mac_address,
            "channel": network.channel
        }
        network_list_serializable.append(network_serializable)

    def safe_get_raw(obj, attr, default=None):
        return getattr(obj, attr, default)

    def safe_replace_and_int(value):
        if value is None or value == '-' or value == 'burn-in':
            return None
        if isinstance(value, str):
            value = value.replace('const', '12887k').replace("k", "").replace("Ω", "")
        return try_int(value)

    # Safe data preparation
    bme_temp_raw = safe_get_raw(data_obj.bme_data, 'temperature_raw')
    bme_hum_raw = safe_get_raw(data_obj.bme_data, 'humidity_raw')
    bme_press_raw = safe_get_raw(data_obj.bme_data, 'pressure_raw')

    data = {
        "timestamp": timestamp,
        "bme_data": {
            "temperature": round(try_float(bme_temp_raw), 4) if bme_temp_raw is not None else None,
            "humidity": round(try_float(bme_hum_raw), 4) if bme_hum_raw is not None else None,
            "pressure": round(try_float(bme_press_raw), 4) if bme_press_raw is not None else None,
            "gas_resistance": safe_replace_and_int(data_obj.bme_data.gas_resistance),
            "air_quality_score": safe_replace_and_int(
                data_obj.bme_data.air_quality_score.replace('%', '') if isinstance(data_obj.bme_data.air_quality_score,
                                                                                   str) else data_obj.bme_data.air_quality_score)
        },
        "pms_data": {
            "pm1_0": try_int(data_obj.pms_data.pm1_0) if data_obj.pms_data.pm1_0 != '-' else None,
            "pm2_5": try_int(data_obj.pms_data.pm2_5) if data_obj.pms_data.pm2_5 != '-' else None,
            "pm10": try_int(data_obj.pms_data.pm10) if data_obj.pms_data.pm10 != '-' else None,
            "p0_3": try_int(data_obj.pms_data.p0_3) if data_obj.pms_data.p0_3 != '-' else None,
            "p0_5": try_int(data_obj.pms_data.p0_5) if data_obj.pms_data.p0_5 != '-' else None,
            "p1_0": try_int(data_obj.pms_data.p1_0) if data_obj.pms_data.p1_0 != '-' else None,
            "p2_5": try_int(data_obj.pms_data.p2_5) if data_obj.pms_data.p2_5 != '-' else None,
            "p5_0": try_int(data_obj.pms_data.p5_0) if data_obj.pms_data.p5_0 != '-' else None,
            "p10": try_int(data_obj.pms_data.p10) if data_obj.pms_data.p10 != '-' else None,
            "aqi_us": try_int(air.calculate_aqi_us(data_obj.pms_data.pm2_5, data_obj.pms_data.pm10)),
            "aqi_eu": try_float(air.calculate_aqi_eu(data_obj.pms_data.pm2_5, data_obj.pms_data.pm10))
        },
        "uv_data": {
            "uvs": try_int(data_obj.uv_data.uvs) if data_obj.uv_data.uvs != '-' else None,
            "als": try_int(data_obj.uv_data.als) if data_obj.uv_data.als != '-' else None
        },
        "wifi_data": {
            "network_list": network_list_serializable
        }
    }

    # Write to JSON if needed
    if write_data:
        write_data_file(data)

    # Write to SQLite
    conn = sqlite3.connect("./data_archive/data.db")
    cursor = conn.cursor()

    # Insert BME data
    cursor.execute('''
        INSERT OR REPLACE INTO bme_data (timestamp, temperature, humidity, pressure, gas_resistance, air_quality_score)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, data["bme_data"]["temperature"], data["bme_data"]["humidity"],
          data["bme_data"]["pressure"], data["bme_data"]["gas_resistance"],
          data["bme_data"]["air_quality_score"]))

    # Insert PMS data
    cursor.execute('''
        INSERT OR REPLACE INTO pms_data (timestamp, pm1_0, pm2_5, pm10, p0_3, p0_5, p1_0, p2_5, p5_0, p10, aqi_us, aqi_eu)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, data["pms_data"]["pm1_0"], data["pms_data"]["pm2_5"], data["pms_data"]["pm10"],
          data["pms_data"]["p0_3"], data["pms_data"]["p0_5"], data["pms_data"]["p1_0"], data["pms_data"]["p2_5"],
          data["pms_data"]["p5_0"], data["pms_data"]["p10"], data["pms_data"]["aqi_us"], data["pms_data"]["aqi_eu"]))

    # Insert UV data
    cursor.execute('''
        INSERT OR REPLACE INTO uv_data (timestamp, uvs, als)
        VALUES (?, ?, ?)
    ''', (timestamp, data["uv_data"]["uvs"], data["uv_data"]["als"]))

    # Insert WiFi data (multiple rows per timestamp if needed)
    for network in data["wifi_data"]["network_list"]:
        cursor.execute('''
            INSERT OR REPLACE INTO wifi_data (timestamp, name, frequency, quality, signal_level, mac_address, channel)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, network["name"], network["frequency"], network["quality"], network["signal_level"],
              network["mac_address"], network["channel"]))

    conn.commit()
    conn.close()

    if return_data:
        return data

# Update current data in both JSON and SQLite formats
def update_current(data_obj):
    data = save_data(data_obj, return_data=True, write_data=False)
    write_current(data)

# Initialize database upon module load
initialize_database()
