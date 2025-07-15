"""
Configuration loader for environment variables and YAML files.
Supports loading from .env files, YAML files, and environment variables.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Lớp tải cấu hình từ nhiều nguồn khác nhau.
    Hỗ trợ .env files, YAML files, và environment variables.
    """
    
    def __init__(self, config_dir: str = "config"):
        """
        Khởi tạo config loader.
        
        Args:
            config_dir: Thư mục chứa các file cấu hình
        """
        self.config_dir = Path(config_dir)
        self._ensure_config_dir()
    
    def _ensure_config_dir(self):
        """Đảm bảo thư mục config tồn tại."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Đã tạo thư mục cấu hình: {self.config_dir}")
    
    def load_env_config(self, env_file: str = "app.env") -> Dict[str, Any]:
        """
        Tải cấu hình từ file .env.
        
        Args:
            env_file: Tên file .env
            
        Returns:
            Dictionary chứa cấu hình
        """
        env_path = self.config_dir / env_file
        
        if not env_path.exists():
            logger.warning(f"File .env không tồn tại: {env_path}")
            return {}
        
        # Load .env file
        load_dotenv(env_path)
        
        # Parse environment variables into structured config
        config = self._parse_env_variables()
        
        logger.info(f"Đã tải cấu hình từ file .env: {env_path}")
        return config
    
    def _parse_env_variables(self) -> Dict[str, Any]:
        """
        Parse các biến môi trường thành cấu hình có cấu trúc.
        
        Returns:
            Dictionary chứa cấu hình được phân tích
        """
        config = {}
        
        # Sensor configuration
        config["sensor"] = {
            "uart_port": os.getenv("SENSOR_UART_PORT", "/dev/ttyUSB0"),
            "baud_rate": int(os.getenv("SENSOR_BAUD_RATE", "115200")),
            "reconnect_delay_s": int(os.getenv("SENSOR_RECONNECT_DELAY_S", "5")),
            "default_output_rate_hz": int(os.getenv("SENSOR_DEFAULT_OUTPUT_RATE_HZ", "200")),
            "default_output_content": {
                "time": self._parse_bool(os.getenv("SENSOR_OUTPUT_TIME", "true")),
                "acceleration": self._parse_bool(os.getenv("SENSOR_OUTPUT_ACCELERATION", "true")),
                "angular_velocity": self._parse_bool(os.getenv("SENSOR_OUTPUT_ANGULAR_VELOCITY", "false")),
                "angle": self._parse_bool(os.getenv("SENSOR_OUTPUT_ANGLE", "false")),
                "magnetic_field": self._parse_bool(os.getenv("SENSOR_OUTPUT_MAGNETIC_FIELD", "false")),
                "port_status": self._parse_bool(os.getenv("SENSOR_OUTPUT_PORT_STATUS", "false")),
                "atmospheric_pressure_height": self._parse_bool(os.getenv("SENSOR_OUTPUT_ATMOSPHERIC_PRESSURE_HEIGHT", "false")),
                "gnss_data": self._parse_bool(os.getenv("SENSOR_OUTPUT_GNSS_DATA", "false")),
                "gnss_speed": self._parse_bool(os.getenv("SENSOR_OUTPUT_GNSS_SPEED", "false")),
                "quaternion": self._parse_bool(os.getenv("SENSOR_OUTPUT_QUATERNION", "false")),
                "gnss_accuracy": self._parse_bool(os.getenv("SENSOR_OUTPUT_GNSS_ACCURACY", "false"))
            }
        }
        
        # Processing configuration
        config["processing"] = {
            "data_buffer_size": int(os.getenv("PROCESSING_DATA_BUFFER_SIZE", "20")),
            "gravity_g": float(os.getenv("PROCESSING_GRAVITY_G", "9.80665")),
            "dt_sensor_actual": float(os.getenv("PROCESSING_DT_SENSOR_ACTUAL", "0.005")),
            "acc_filter_type": os.getenv("PROCESSING_ACC_FILTER_TYPE", "low_pass"),
            "acc_filter_param": float(os.getenv("PROCESSING_ACC_FILTER_PARAM", "0.1")),
            "rls_sample_frame_size": int(os.getenv("PROCESSING_RLS_SAMPLE_FRAME_SIZE", "20")),
            "rls_calc_frame_multiplier": int(os.getenv("PROCESSING_RLS_CALC_FRAME_MULTIPLIER", "100")),
            "rls_filter_q": float(os.getenv("PROCESSING_RLS_FILTER_Q", "0.9875")),
            "fft_n_points": int(os.getenv("PROCESSING_FFT_N_POINTS", "512")),
            "fft_min_freq_hz": float(os.getenv("PROCESSING_FFT_MIN_FREQ_HZ", "0.1")),
            "fft_max_freq_hz": self._parse_float_or_none(os.getenv("PROCESSING_FFT_MAX_FREQ_HZ", "null"))
        }
        
        # Process control configuration
        config["process_control"] = {
            "decoding": self._parse_bool(os.getenv("PROCESS_CONTROL_DECODING", "true")),
            "processing": self._parse_bool(os.getenv("PROCESS_CONTROL_PROCESSING", "true")),
            "mqtt_sending": self._parse_bool(os.getenv("PROCESS_CONTROL_MQTT_SENDING", "true")),
            "mqtt_mode": os.getenv("PROCESS_CONTROL_MQTT_MODE", "continuous")  # continuous or scheduled
        }
        
        # Data compression configuration
        config["data_compression"] = {
            "format": os.getenv("DATA_COMPRESSION_FORMAT", "json"),
            "use_zlib": self._parse_bool(os.getenv("DATA_COMPRESSION_USE_ZLIB", "false"))
        }
        
        # Data storage configuration
        config["data_storage"] = {
            "enabled": self._parse_bool(os.getenv("DATA_STORAGE_ENABLED", "true")),
            "immediate_transmission": self._parse_bool(os.getenv("DATA_STORAGE_IMMEDIATE_TRANSMISSION", "true")),
            "batch_transmission_size": int(os.getenv("DATA_STORAGE_BATCH_TRANSMISSION_SIZE", "50")),
            "base_dir": os.getenv("DATA_STORAGE_BASE_DIR", "data"),
            "format": os.getenv("DATA_STORAGE_FORMAT", "csv"),
            "max_file_size_mb": float(os.getenv("DATA_STORAGE_MAX_FILE_SIZE_MB", "10.0")),
            "session_prefix": os.getenv("DATA_STORAGE_SESSION_PREFIX", "session")
        }
        
        # Cleanup configuration
        config["cleanup"] = {
            "enabled": self._parse_bool(os.getenv("CLEANUP_ENABLED", "true")),
            "schedule_hours": int(os.getenv("CLEANUP_SCHEDULE_HOURS", "24")),
            "logs_retention_days": int(os.getenv("CLEANUP_LOGS_RETENTION_DAYS", "7")),
            "data_retention_days": int(os.getenv("CLEANUP_DATA_RETENTION_DAYS", "30"))
        }
        
        # Scheduled MQTT configuration
        config["scheduled_mqtt"] = {
            "enabled": self._parse_bool(os.getenv("SCHEDULED_MQTT_ENABLED", "false")),
            "interval_seconds": int(os.getenv("SCHEDULED_MQTT_INTERVAL_SECONDS", "60")),
            "data_source_dir": os.getenv("SCHEDULED_MQTT_DATA_SOURCE_DIR", "data/processed_data"),
            "batch_size": int(os.getenv("SCHEDULED_MQTT_BATCH_SIZE", "100")),
            "delete_after_send": self._parse_bool(os.getenv("SCHEDULED_MQTT_DELETE_AFTER_SEND", "false")),
            "mqtt_topic": os.getenv("SCHEDULED_MQTT_TOPIC", "sensor/batch_data")
        }
        
        return config
    
    def load_yaml_config(self, yaml_file: str) -> Dict[str, Any]:
        """
        Tải cấu hình từ file YAML.
        
        Args:
            yaml_file: Tên file YAML
            
        Returns:
            Dictionary chứa cấu hình
        """
        yaml_path = self.config_dir / yaml_file
        
        if not yaml_path.exists():
            logger.warning(f"File YAML không tồn tại: {yaml_path}")
            return {}
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            logger.info(f"Đã tải cấu hình từ file YAML: {yaml_path}")
            return config or {}
            
        except yaml.YAMLError as e:
            logger.error(f"Lỗi khi đọc file YAML {yaml_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Lỗi không xác định khi tải file YAML {yaml_path}: {e}")
            return {}
    
    def load_json_config(self, json_file: str) -> Dict[str, Any]:
        """
        Tải cấu hình từ file JSON (để tương thích ngược).
        
        Args:
            json_file: Tên file JSON
            
        Returns:
            Dictionary chứa cấu hình
        """
        json_path = self.config_dir / json_file
        
        if not json_path.exists():
            logger.warning(f"File JSON không tồn tại: {json_path}")
            return {}
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            logger.info(f"Đã tải cấu hình từ file JSON: {json_path}")
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi JSON trong file {json_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Lỗi không xác định khi tải file JSON {json_path}: {e}")
            return {}
    
    def load_all_configs(self) -> Dict[str, Any]:
        """
        Tải tất cả các cấu hình từ các file khác nhau.
        
        Returns:
            Dictionary chứa tất cả cấu hình
        """
        # Load main configuration from .env
        config = self.load_env_config()
        
        # Load logging configuration from YAML
        logging_config = self.load_yaml_config("logging.yaml")
        if logging_config:
            config["logging"] = logging_config.get("logging", {})
        
        # Load MQTT configuration from YAML
        mqtt_config = self.load_yaml_config("mosquitto.yaml")
        if mqtt_config:
            # Transform YAML structure to expected format for backward compatibility
            yaml_mqtt = mqtt_config.get("mqtt", {})
            config["mqtt"] = self._transform_mqtt_config(yaml_mqtt)
        
        # Load message configuration from JSON (for backward compatibility)
        message_config = self.load_json_config("mqtt_message_config.json")
        if message_config:
            config["mqtt_message"] = message_config
        
        return config
    
    def _transform_mqtt_config(self, yaml_mqtt: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform YAML MQTT configuration structure to the format expected by MQTT publishers.
        
        Args:
            yaml_mqtt: MQTT configuration from YAML file
            
        Returns:
            Transformed MQTT configuration
        """
        transformed = {}
        
        # Broker settings
        broker = yaml_mqtt.get("broker", {})
        transformed["broker_address"] = broker.get("address", "localhost")
        transformed["broker_port"] = broker.get("port", 1883)
        transformed["keepalive"] = broker.get("keepalive", 60)
        
        # Client settings
        client = yaml_mqtt.get("client", {})
        transformed["client_id"] = client.get("id", "rpi_hwt905_backend_client")
        
        # Authentication settings
        auth = yaml_mqtt.get("auth", {})
        transformed["use_tls"] = auth.get("use_tls", False)
        transformed["username"] = auth.get("username", "")
        transformed["password"] = auth.get("password", "")
        
        # Topic settings
        topics = yaml_mqtt.get("topics", {})
        transformed["publish_data_topic"] = topics.get("publish_data", "sensor/hwt905/processed_data")
        transformed["subscribe_commands_topic"] = topics.get("subscribe_commands", "sensor/hwt905/commands")
        transformed["publish_status_topic"] = topics.get("publish_status", "sensor/hwt905/status")
        transformed["publish_response_topic"] = topics.get("publish_response", "sensor/hwt905/config_response")
        
        # Send strategy settings
        send_strategy = yaml_mqtt.get("send_strategy", {})
        transformed["send_strategy"] = {
            "type": send_strategy.get("type", "realtime"),
            "batch_size": send_strategy.get("batch_size", 100),
            "batch_timeout": send_strategy.get("batch_timeout", 5.0)
        }
        
        return transformed
    
    def _parse_bool(self, value: str) -> bool:
        """Parse string to boolean."""
        if isinstance(value, bool):
            return value
        return value.lower() in ("true", "1", "yes", "on")
    
    def _parse_float_or_none(self, value: str) -> Optional[float]:
        """Parse string to float or None."""
        if value.lower() in ("null", "none", ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None


# Singleton instance
_config_loader = ConfigLoader()

def load_config(config_type: str = "all") -> Dict[str, Any]:
    """
    Tải cấu hình theo loại được chỉ định.
    
    Args:
        config_type: Loại cấu hình cần tải ("all", "env", "logging", "mqtt", "message")
        
    Returns:
        Dictionary chứa cấu hình
    """
    global _config_loader
    
    if config_type == "all":
        return _config_loader.load_all_configs()
    elif config_type == "env":
        return _config_loader.load_env_config()
    elif config_type == "logging":
        return _config_loader.load_yaml_config("logging.yaml")
    elif config_type == "mqtt":
        return _config_loader.load_yaml_config("mosquitto.yaml")
    elif config_type == "message":
        return _config_loader.load_json_config("mqtt_message_config.json")
    else:
        logger.error(f"Loại cấu hình không hỗ trợ: {config_type}")
        return {}

# Legacy function for backward compatibility
def load_config_legacy(file_path: str) -> Dict[str, Any]:
    """
    Tải cấu hình từ file JSON (legacy function).
    
    Args:
        file_path: Đường dẫn đến file cấu hình
        
    Returns:
        Dictionary chứa cấu hình
    """
    full_path = Path(file_path)
    if not full_path.exists():
        logger.error(f"File cấu hình không tìm thấy: {full_path}")
        return {}
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Lỗi cú pháp JSON trong file {full_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Lỗi khi tải file cấu hình {full_path}: {e}")
        return {} 