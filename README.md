# HWT905 RaspberryPi Sensor Data Processing System

## Overview

This is a comprehensive embedded sensor data processing system designed specifically for **Raspberry Pi** environments. The system processes acceleration data from **HWT905** 9-axis IMU sensors, performs real-time signal processing, and transmits data via **MQTT** with robust storage capabilities for intermittent connectivity scenarios.

### Key Features

- **Real-time Sensor Data Processing**: Handles HWT905 9-axis IMU data at up to 200Hz sampling rate
- **Advanced Signal Processing**: RLS (Recursive Least Squares) integration and FFT analysis
- **Robust Storage System**: Local data storage with configurable formats (CSV/JSON) for offline operation
- **MQTT Connectivity**: Real-time data transmission with automatic reconnection
- **Auto-Reconnection**: Intelligent sensor connection recovery with automatic thread management
- **Intermittent Connectivity Support**: Batch transmission capabilities for unstable network environments
- **Remote Configuration**: Standalone MQTT service for field-configurable sensor parameters
- **Embedded-Optimized**: Designed for resource-constrained environments like Raspberry Pi

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   HWT905 IMU    │────│  Data Processor  │────│  Storage System │
│   (UART/USB)    │    │  - RLS Filter    │    │  - CSV/JSON     │
└─────────────────┘    │  - FFT Analysis  │    │  - Batch Ready  │
                       │  - Real-time     │    └─────────────────┘
                                  │                     │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MQTT Broker   │────│   MQTT Client    │────│  Data Transmit  │
│  (External)     │    │  - Auto Retry    │    │  - Immediate    │
└─────────────────┘    │  - TLS Support   │    │  - Batch Mode   │
                       └──────────────────┘    └─────────────────┘
```

## Hardware Requirements

### Minimum Requirements
- **Raspberry Pi 3B+** or newer
- **8GB microSD card** (Class 10 or better)
- **HWT905 9-axis IMU sensor**
- **Stable 5V 2.5A power supply**

### Recommended for Production
- **Raspberry Pi 4B** (4GB RAM)
- **32GB microSD card** (Application Class 2)
- **Ethernet connection** (for stable MQTT connectivity)
- **Real-time clock module** (RTC) for accurate timestamps

### Sensor Connection
- **UART Connection**: Connect HWT905 to Pi's GPIO pins
  - `VCC` → `5V` (Pin 2)
  - `GND` → `GND` (Pin 6)
  - `TX` → `RX` (GPIO 15, Pin 10)
  - `RX` → `TX` (GPIO 14, Pin 8)
- **USB Connection**: Use HWT905 USB adapter (plug-and-play)

## Installation

### 1. System Prerequisites

```bash
# Update Raspberry Pi OS
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+ and pip
sudo apt install python3 python3-pip python3-venv git -y

# Enable UART (for direct sensor connection)
sudo raspi-config
# Navigate to: Interface Options > Serial Port
# Enable serial port, disable login shell over serial
```

### 2. Project Setup

```bash
# Clone the repository
git clone <repository-url>
cd hwt905-raspi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p data/processed_data data/sensor_logs logs
```

### 3. Configuration

Copy and customize the configuration files:

```bash
# Review and modify sensor settings
nano config/app_config.json

# Configure MQTT broker settings
nano config/mqtt_message_config.json
```

## Configuration

### Main Configuration (`config/app_config.json`)

```json
{
  "sensor": {
    "uart_port": "/dev/ttyAMA0",
    "baud_rate": 9600,
    "default_output_rate_hz": 200
  },
  "processing": {
    "dt_sensor_actual": 0.005,
    "gravity_g": 9.81,
    "rls_sample_frame_size": 20,
    "fft_n_points": 512
  },
  "data_storage": {
    "enabled": true,
    "immediate_transmission": true,
    "batch_transmission_size": 50,
    "base_dir": "data/processed_data",
    "format": "csv",
    "max_file_size_mb": 10
  },
  "mqtt": {
    "broker_address": "your-mqtt-broker.com",
    "broker_port": 1883,
    "client_id": "raspi-hwt905-001",
    "use_tls": false
  }
}
```

### Key Configuration Options

#### Storage System
- **`enabled`**: Enable/disable local data storage
- **`immediate_transmission`**: Send data immediately (true) or storage-only mode (false)
- **`batch_transmission_size`**: Number of records per batch for offline transmission
- **`format`**: Data storage format (`csv` or `json`)
- **`max_file_size_mb`**: Maximum file size before rotation

#### Sensor Processing
- **`default_output_rate_hz`**: Sensor sampling rate (10, 50, 100, 200 Hz)
- **`rls_sample_frame_size`**: RLS processing frame size (affects latency vs accuracy)
- **`fft_n_points`**: FFT analysis resolution (512, 1024, 2048)

## Usage

### Operating Modes

The system supports three operating modes for different deployment scenarios:

#### 1. Realtime Mode (Default)
Gửi dữ liệu ngay lập tức khi được xử lý:
```bash
# Chạy trực tiếp
python main.py --mode realtime

# Hoặc sử dụng các option bổ sung
python main.py --mode realtime --debug
```

#### 2. Batch Mode
Thu thập dữ liệu và gửi theo batch để tối ưu hóa băng thông:
```bash
# Chạy với batch size mặc định
python main.py --mode batch

# Tùy chỉnh batch size
python main.py --mode batch --batch-size 50
```

#### 3. Scheduled Mode
Gửi dữ liệu theo lịch trình định kỳ (thích hợp cho môi trường mạng không ổn định):
```bash
# Chạy với interval mặc định (60s)
python main.py --mode scheduled

# Tùy chỉnh interval
python main.py --mode scheduled --schedule-interval 120
```

### Command Line Options

```bash
# Tắt các chức năng cụ thể
python main.py --no-decode    # Tắt giải mã dữ liệu
python main.py --no-process   # Tắt xử lý dữ liệu
python main.py --no-mqtt      # Tắt gửi MQTT
python main.py --no-storage   # Tắt lưu trữ dữ liệu

# Kết hợp các option
python main.py --mode batch --batch-size 100 --debug --no-storage
```

### SystemD Service Deployment

#### Cài đặt Service

```bash
# Chạy script cài đặt tương tác
sudo ./scripts/install.sh

# Hoặc cài đặt trực tiếp cho chế độ cụ thể
sudo cp systemd/hwt905-raspi.service /etc/systemd/system/          # Realtime mode
sudo cp systemd/hwt905-raspi-batch.service /etc/systemd/system/    # Batch mode
sudo cp systemd/hwt905-raspi-scheduled.service /etc/systemd/system/ # Scheduled mode

sudo systemctl daemon-reload
```

#### Quản lý Service

```bash
# Khởi động service
sudo systemctl start hwt905-raspi                # Realtime mode
sudo systemctl start hwt905-raspi-batch          # Batch mode
sudo systemctl start hwt905-raspi-scheduled      # Scheduled mode

# Bật tự động khởi động cùng hệ thống
sudo systemctl enable hwt905-raspi

# Kiểm tra trạng thái
sudo systemctl status hwt905-raspi

# Xem log
sudo journalctl -u hwt905-raspi -f
```

### Basic Operation

```bash
# Activate virtual environment
source venv/bin/activate

# Run the main application using startup script
scripts/run_app.sh

# Or run directly with mode selection
python main.py --mode realtime

# Run with debug logging
python main.py --mode batch --debug
```

### Sensor Configuration

Use the dedicated configuration tool for sensor setup:

```bash
# Read current sensor configuration
python3 scripts/config_tool.py --info

# Set output rate to 200 Hz
python3 scripts/config_tool.py --rate 200

# Set output content (acceleration and time data)
python3 scripts/config_tool.py --output acc,time

# Change baudrate to 115200
python3 scripts/config_tool.py --baudrate 115200

# Perform factory reset
python3 scripts/config_tool.py --factory-reset
```

### Remote Configuration via MQTT

The system includes a **standalone MQTT Configuration Service** that runs independently from the main application, allowing remote sensor configuration while the system operates in the field.

#### Starting the Services

```bash
# 1. Start main data logging application
./scripts/run_app.sh

# 2. Start MQTT config service (in separate terminal)
./scripts/start_mqtt_config.sh

# Or run directly with options
python3 scripts/mqtt_config_service.py --log-level INFO
```

#### Service Architecture

```
┌─────────────────┐    ┌─────────────────┐
│  Main App       │    │ MQTT Config     │
│ (Data Logging)  │    │ Service         │
│                 │    │ (Remote Config) │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          └──────┬──────┬────────┘
                 │      │
         ┌───────▼──────▼───────┐
         │    HWT905 Sensor     │
         └──────────────────────┘
```

#### MQTT Configuration Commands

```bash
# Test MQTT configuration interactively
python3 scripts/mqtt_config_tester.py --broker localhost --interactive

# Send specific commands via MQTT
mosquitto_pub -h localhost -t "hwt905/commands" -m '{"command":"read_config"}'
```

#### Supported Commands

```json
// Set output rate to 200 Hz
{
  "command": "set_rate",
  "value": 200
}

// Configure output data types
{
  "command": "set_output",
  "acceleration": true,
  "gyroscope": true,
  "angle": true,
  "magnetic": false
}

// Change sensor baudrate
{
  "command": "set_baudrate", 
  "value": 115200
}

// Factory reset sensor
{
  "command": "factory_reset"
}

// Read current configuration
{
  "command": "read_config"
}

// Send raw hex commands
{
  "command": "raw_hex",
  "data": "FF AA 27 19 00"
}
```

#### Web Interface

Open `templates/mqtt_config.html` in a web browser for a graphical interface to control the sensor remotely.

**📋 See [MQTT_CONFIG_SERVICE.md](MQTT_CONFIG_SERVICE.md) for detailed documentation.**

### Mock Data Testing

For development without physical hardware:

```bash
# Enable mock data in config/app_config.json
"mock_data": true

# Run with simulated sensor data
python main.py
```

### Storage Management

```bash
# Monitor real-time data storage
python scripts/data_manager.py monitor

# View storage statistics
python scripts/data_manager.py stats

# Clean up old data files
python scripts/data_manager.py cleanup --days 7
```

### Demo and Testing

```bash
# Run storage system demo
python scripts/demo_storage.py

# Run integration tests
python scripts/test_integration.py
```

## Data Processing Pipeline

### 1. Raw Data Acquisition
- **Sensor Reading**: 200Hz acceleration data (X, Y, Z axes)
- **Data Validation**: Checksum verification and packet integrity
- **Unit Conversion**: Convert from sensor units (g) to SI units (m/s²)

### 2. Signal Processing
- **Pre-filtering**: Optional moving average or low-pass filtering
- **RLS Integration**: Recursive Least Squares for velocity and displacement calculation
- **FFT Analysis**: Frequency domain analysis for vibration characterization
- **Feature Extraction**: Dominant frequencies and magnitude calculations

### 3. Data Storage
- **Real-time Storage**: Processed data saved to local files
- **Format Options**: CSV (human-readable) or JSON (structured)
- **File Management**: Automatic rotation based on size/time limits
- **Batch Preparation**: Data organized for efficient transmission

### 4. MQTT Transmission
- **Immediate Mode**: Real-time transmission with local backup
- **Batch Mode**: Store locally, transmit when connectivity available
- **Data Compression**: Optional zlib compression for bandwidth efficiency
- **QoS Control**: Configurable MQTT Quality of Service levels

## Data Formats

### CSV Output Format
```csv
timestamp,acc_x,acc_y,acc_z,acc_x_filtered,acc_y_filtered,acc_z_filtered,vel_x,vel_y,vel_z,disp_x,disp_y,disp_z,displacement_magnitude,dominant_freq_x,dominant_freq_y,dominant_freq_z,overall_dominant_frequency,rls_warmed_up
1672531200.123,0.05,-0.02,9.78,0.048,-0.018,9.776,0.001,0.0005,0.002,0.00001,0.000005,0.00002,0.000025,1.2,0.8,1.5,1.5,true
```

### JSON Output Format
```json
{
  "timestamp": 1672531200.123,
  "acceleration": {
    "raw": {"x": 0.05, "y": -0.02, "z": 9.78},
    "filtered": {"x": 0.048, "y": -0.018, "z": 9.776}
  },
  "velocity": {"x": 0.001, "y": 0.0005, "z": 0.002},
  "displacement": {
    "x": 0.00001, "y": 0.000005, "z": 0.00002,
    "magnitude": 0.000025
  },
  "frequency_analysis": {
    "dominant_frequencies": {"x": 1.2, "y": 0.8, "z": 1.5},
    "overall_dominant": 1.5
  },
  "rls_warmed_up": true
}
```

## Changelog

### v2.2.0 (Latest) - Startup Optimization & Config Management
- **Startup Performance**: Removed unnecessary sensor reconfiguration on every startup for faster boot times
- **Configuration Tool**: Added dedicated `sensor_config_tool.py` for standalone sensor configuration
- **Better Separation**: Clean separation between operational runtime and configuration management
- **Reduced Log Noise**: Eliminated configuration steps from normal operation logs

### v2.1.0 - Error Handling & Stability Fixes
- **Fixed Errno 5 Spam**: Added proper throttling for OSError (including Input/Output errors) to prevent log spam when sensor is disconnected
- **Improved Ctrl+C Handling**: Enhanced signal handling to ensure application stops with single Ctrl+C press
- **Better Connection Loss Detection**: SerialReaderThread now properly detects and handles connection loss
- **Virtual Environment Support**: Added setup scripts for better dependency management

### v2.0.0 - MQTT & Pipeline Refactoring
- **MQTT Module Refactor**: Re-architected the MQTT client into a modular, strategy-based publisher (`BasePublisher`, `RealtimePublisher`, `BatchPublisher`, `PublisherFactory`).
- **Asynchronous Pipeline**: Enhanced the data pipeline to four independent threads (`Reader` -> `Decoder` -> `Processor` -> `MqttPublisher`) using Queues for non-blocking, high-throughput operation.
- **Configurable Payloads & Compression**:
  - Implemented logic to send lean/customized MQTT payloads (e.g., only displacement and FFT results).
  - Integrated `zlib` and `msgpack` for efficient, configurable data compression.
- **Bug Fixes**: Resolved serialization (`KeyError`, `numpy.ndarray`) and import (`NameError`) errors for both `batch` and `realtime` MQTT strategies.

### v1.0.0 - Initial Release
- Initial implementation of the data processing system.
- Supports reading from HWT905 sensor.
- Includes RLS and FFT algorithms.
- Basic local CSV storage.

## Troubleshooting

### Common Issues

#### Sensor Connection Problems
```bash
# Check UART is enabled
sudo dmesg | grep tty

# Test serial port
sudo minicom -D /dev/ttyAMA0 -b 9600

# Check permissions
sudo usermod -a -G dialout $USER
```

#### MQTT Connection Issues
```bash
# Test MQTT broker connectivity
sudo apt install mosquitto-clients
mosquitto_pub -h your-broker.com -t test/topic -m "test message"

# Check network connectivity
ping your-broker.com
```

#### Storage Space Issues
```bash
# Check available space
df -h

# Monitor data directory size
du -sh data/processed_data/

# Clean up old files
find data/processed_data/ -name "*.csv" -mtime +7 -delete
```

#### Performance Issues
```bash
# Monitor CPU usage
htop

# Check memory usage
free -h

# Monitor I/O
sudo iotop
```

### Log Analysis

```bash
# View application logs
tail -f logs/application.log

# Search for errors
grep -i error logs/application.log

# Monitor real-time processing
grep "processed.*samples" logs/application.log
```

## Production Deployment

### System Service Setup

Create a systemd service for automatic startup:

```bash
# Create service file
sudo nano /etc/systemd/system/hwt905-sensor.service
```

```ini
[Unit]
Description=HWT905 Sensor Data Processing
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/hwt905-raspi
Environment=PATH=/home/pi/hwt905-raspi/venv/bin
ExecStart=/home/pi/hwt905-raspi/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable hwt905-sensor.service
sudo systemctl start hwt905-sensor.service

# Check status
sudo systemctl status hwt905-sensor.service
```

### Monitoring and Maintenance

```bash
# Setup log rotation
sudo nano /etc/logrotate.d/hwt905-sensor

# Monitor service health
sudo systemctl status hwt905-sensor.service

# View service logs
sudo journalctl -u hwt905-sensor.service -f
```

### Performance Optimization

```bash
# Increase swap for stability
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Optimize for real-time processing
echo 'kernel.sched_rt_runtime_us = -1' | sudo tee -a /etc/sysctl.conf
```

## API Reference

### SensorDataProcessor Class

Main data processing class with integrated storage capabilities.

```python
from src.processing.data_processor import SensorDataProcessor

processor = SensorDataProcessor(
    dt_sensor=0.005,           # 200Hz sampling rate
    gravity_g=9.81,            # Earth gravity
    storage_config={           # Storage configuration
        "enabled": True,
        "format": "csv",
        "base_dir": "data/processed_data"
    }
)

# Process new sensor sample
result = processor.process_new_sample(acc_x_g, acc_y_g, acc_z_g)

# Get batch data for offline transmission
batch_data = processor.get_batch_for_transmission()

# Clean up resources
processor.close()
```

### Storage Manager

Direct access to storage functionality.

```python
from src.processing.data_storage import StorageManager

storage = StorageManager({
    "enabled": True,
    "format": "csv",
    "max_file_size_mb": 10
})

# Store processed data
storage.store_processed_data(data, timestamp)

# Retrieve batch for transmission
batch = storage.get_batch_for_transmission()
```

## Contributing

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black src/ scripts/
flake8 src/ scripts/
```

### Code Structure

```
src/
├── processing/          # Data processing modules
│   ├── data_processor.py     # Main processor with storage
│   ├── data_storage.py       # Storage management
│   ├── data_filter.py        # Signal filtering
│   └── algorithms/           # Processing algorithms
├── sensors/             # Sensor communication
├── mqtt/               # MQTT client
├── core/               # Main application logic
└── utils/              # Utility functions

scripts/                # Management and demo scripts
config/                 # Configuration files
data/                   # Data storage directory
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For technical support or questions:
- Create an issue in the project repository
- Review the troubleshooting section above
- Check the logs for detailed error information

### System Health Check

Before deployment, run the system health check to ensure everything is properly configured:

```bash
# Run comprehensive system check
./scripts/system_check.sh

# This will verify:
# ✅ File permissions and directory structure
# ✅ Python dependencies and imports  
# ✅ Configuration file validity
# ✅ System resources and USB devices
# ✅ Basic functionality tests
```

**Output Example:**
```
✅ System health check completed
🚀 System ready for operation
📋 Quick Start Commands:
   Start main app:          ./scripts/run_app.sh
   Test auto-reconnection:  ./scripts/test_auto_reconnection.sh
```

#### Testing Auto-Reconnection

Use the provided test script to verify auto-reconnection functionality:

```bash
# Interactive test mode (recommended)
./scripts/test_auto_reconnection.sh

# Monitor logs only
./scripts/test_auto_reconnection.sh monitor

# Automated test (60-second monitoring window)
./scripts/test_auto_reconnection.sh auto

# Check current USB devices
./scripts/test_auto_reconnection.sh devices
```

**Test Procedure:**
1. Start the main application
2. Wait for successful sensor connection
3. Physically disconnect the USB sensor cable
4. Observe automatic detection of connection loss
5. Reconnect the USB cable
6. Verify automatic reconnection and system recovery

**Expected Log Output:**
```
🔄 Bắt đầu quá trình kết nối lại...
✅ Cảm biến đã được kết nối lại thành công!
✅ Đã kết nối lại thành công và khởi động lại hệ thống!
```