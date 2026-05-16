# Raspberry Pi Zero sensor driver script

A compact, headless environmental monitoring system built with a Raspberry Pi Zero WH.  
It reads data from BME680, PMS9103M, and LTR390 sensors, displays live readings on a 1.47″ LCD, and archives everything to SQLite and JSON.

## Features

- **BME680** – temperature, humidity, pressure, gas resistance, indoor air quality (IAQ)
- **PMS9103M** – PM1.0, PM2.5, PM10 & particle counts (0.3 µm → 10 µm)
- **LTR390** – UV index & ambient light (Waveshare UV Sensor C)
- **AQI** – US and EU indices calculated from PM measurements
- **Wi‑Fi scanner** – shows nearby networks with signal strength
- **5‑button menu** on a 1.47″ SPI LCD (172×320)
- **Data logging** – SQLite database + JSON files, updated every minute
- **System control** – restart the script, shutdown or reboot the OS from the menu

## Hardware

| Component               | Model / Notes                                |
| ----------------------- | -------------------------------------------- |
| Main board              | Raspberry Pi Zero WH (GPIO headers, Wi‑Fi)   |
| Environmental sensor    | Generic BME680 (I2C, 0x76 / 0x77)            |
| Particulate sensor      | Plantower PMS9103M (UART)                    |
| UV / Ambient light      | Waveshare UV Sensor (C) – LTR390 (I2C, 0x53) |
| Display                 | Waveshare 1.47″ LCD Module (SPI)             |
| Buttons                 | 5 × generic tactile buttons (active low)     |

## Wiring

### Display (SPI)

| LCD Pin | Raspberry Pi GPIO (BCM) |
| ------- | ----------------------- |
| RST     | 27                      |
| DC      | 25                      |
| BL      | 18                      |
| SPI bus | SPI0 (CE0, MOSI, MISO, SCLK) |

The library uses bus=0, device=0.

### Sensors (I2C)

| Sensor | I2C Bus | Address                 |
| ------ | ------- | ----------------------- |
| BME680 | I2C1    | 0x76 (primary) / 0x77   |
| LTR390 | I2C1    | 0x53                    |

### PMS9103M (UART)

- Primary: `/dev/ttyS0` (Pi Zero UART after enabling)
- Fallback: `/dev/ttyAMA0`

### Buttons (GPIO, internal pull‑up)

| Function | GPIO (BCM) |
| -------- | ----------- |
| LEFT     | 12          |
| RIGHT    | 26          |
| UP       | 21          |
| DOWN     | 16          |
| OK       | 20          |

Connect each button between its GPIO pin and GND.

## Usage

After boot, the LCD shows the main overview.

- **Menu 0** – Temperature, humidity, pressure, UV, ambient light, IAQ, PM2.5, PM10, AQI (US & EU)
- **Menu 1** – All PM sizes, particle counts and gas resistance
- **Menu 2** – Wi‑Fi scanner (press OK to start scan)
- **Menu 3** – System commands (Restart SENSE, Shutdown OS, Reboot OS)

Navigate with **LEFT / RIGHT**, scroll with **UP / DOWN**, select with **OK**.

## Project Structure

- **main.py** – Main loop, button handling, data unpacking
- **screen.py** – LCD driver (SPI), drawing & menu rendering
- **env.py** – BME680 driver, burn‑in, IAQ calculation
- **air.py** – PMS9103 UART reader, frame validation, AQI
- **uv.py** – LTR390 UV sensor driver
- **wifi.py** – Wi‑Fi scanner (iwlist)
- **archiver.py** – SQLite & JSON archiving
- **lib/** – LCD_1inch47 library (Waveshare)
- **Font/** – OpenSans font for the LCD
- **data_archive/** – Runtime output (data.db, current.json, data.json)

## Known Limitations & To‑Do

- No physical enclosure (3D‑printed case planned)
- Wi‑Fi scan uses deprecated `iwlist`; consider switching to `iw dev scan`
- Burn‑in and IAQ algorithm are simplified
- No remote dashboard – data is only local
- Wiring is not yet documented as a schematic

## Acknowledgements

This project uses the Waveshare LCD library (`lib/`) which is licensed under the MIT License.
See the [NOTICE](NOTICE) file for details.
