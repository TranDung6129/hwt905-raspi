# src/mqtt/base_publisher.py
import paho.mqtt.client as mqtt
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BasePublisher:
    """
    Lớp cơ sở cho các MQTT publisher, quản lý kết nối và các cấu hình cơ bản.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = mqtt.Client(client_id=config.get("client_id", ""), protocol=mqtt.MQTTv311, transport="tcp")
        
        username = config.get("username")
        if username:
            self.client.username_pw_set(username, config.get("password"))
            
        if config.get("use_tls", False):
            self.client.tls_set()

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        
        self.broker_address = config["broker_address"]
        self.broker_port = config["broker_port"]
        self.keepalive = config["keepalive"]
        self.publish_topic = config["publish_data_topic"]

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Kết nối thành công tới MQTT Broker tại {self.broker_address}:{self.broker_port}")
        else:
            logger.error(f"Kết nối MQTT thất bại, mã lỗi: {rc}")

    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"Đã ngắt kết nối khỏi MQTT Broker. Mã lỗi: {rc}. Đang thử kết nối lại...")
        # Paho-mqtt tự động xử lý việc kết nối lại

    def connect(self):
        """
        Thực hiện kết nối tới MQTT Broker.
        """
        try:
            self.client.connect(self.broker_address, self.broker_port, self.keepalive)
            self.client.loop_start() # Bắt đầu vòng lặp mạng trong một thread riêng
            logger.info("Đã bắt đầu vòng lặp mạng MQTT.")
        except ConnectionRefusedError:
            logger.error(f"Kết nối tới MQTT broker tại {self.broker_address}:{self.broker_port} bị từ chối.")
        except OSError as e:
            logger.error(f"Lỗi mạng khi kết nối tới MQTT broker: {e}")
        except Exception as e:
            logger.error(f"Lỗi không xác định khi kết nối MQTT: {e}")

    def disconnect(self):
        """
        Ngắt kết nối khỏi MQTT Broker một cách an toàn.
        """
        logger.info("Đang ngắt kết nối khỏi MQTT broker...")
        self.client.loop_stop() # Dừng vòng lặp mạng
        self.client.disconnect()
        logger.info("Đã ngắt kết nối MQTT.")

    def publish(self, payload: bytes):
        """
        Gửi một payload tới topic đã cấu hình.
        Đây là phương thức trừu tượng, cần được cài đặt ở các lớp con.
        """
        raise NotImplementedError("Phương thức `publish` phải được cài đặt ở lớp con.")

    def get_compressor(self):
        """
        Lấy một instance của DataCompressor nếu được cấu hình.
        """
        # Tránh import vòng tròn
        from src.processing.data_compressor import DataCompressor
        from src.utils.common import load_config
        
        app_config = load_config() 
        compression_config = app_config.get('data_compression', {})
        if compression_config:
            return DataCompressor(
                format=compression_config.get('format', 'json'),
                use_zlib=compression_config.get('use_zlib', False)
            )
        return None 