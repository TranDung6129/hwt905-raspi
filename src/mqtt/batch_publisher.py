# src/mqtt/batch_publisher.py
import logging
import time
from typing import Dict, Any, List
from .base_publisher import BasePublisher
from src.utils.common import load_config
import paho.mqtt.client as mqtt
import copy

logger = logging.getLogger(__name__)

class BatchPublisher(BasePublisher):
    """
    Publisher thu thập dữ liệu và gửi đi theo từng lô (batch).
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.batch_size = config.get("send_strategy", {}).get("batch_size", 100)
        self.buffer: List[Dict[str, Any]] = []
        self.compressor = self.get_compressor()
        app_config = load_config()  # Sử dụng hệ thống cấu hình mới
        message_config = app_config.get('mqtt_message', {})
        self.message_template = message_config.get('message_templates', {}).get('batch', {}).get('structure', {})
        
        # Throttling cho warning về unpublished messages
        self._last_warning_time = 0
        self._warning_log_delay = 5  # Chỉ log warning mỗi 5 giây
        self._unpublished_mids = []  # Lưu trữ các Mid chưa được publish

    def publish(self, data_point: Dict[str, Any]):
        """
        Thêm một điểm dữ liệu vào buffer. Nếu buffer đầy, gửi cả lô đi.

        Args:
            data_point (Dict[str, Any]): Dữ liệu đã xử lý.
        """
        self.buffer.append(data_point)
        if len(self.buffer) >= self.batch_size:
            self.send_batch()

    def send_batch(self):
        """
        Xây dựng, nén và gửi lô dữ liệu hiện tại trong buffer.
        """
        if not self.buffer:
            return

        logger.debug(f"Buffer đã đầy ({len(self.buffer)}/{self.batch_size}). Chuẩn bị gửi batch.")
        
        # Tạo message từ template, deepcopy để đảm bảo metadata không bị ảnh hưởng lẫn nhau
        message = copy.deepcopy(self.message_template)
        message['metadata']['sample_count'] = len(self.buffer)
        message['metadata']['start_time'] = self.buffer[0].get('ts', 0)
        message['metadata']['end_time'] = self.buffer[-1].get('ts', 0)
        message['data_points'] = self.buffer

        try:
            if self.compressor:
                payload = self.compressor.compress(message)
            else:
                # Fallback to plain JSON
                import json
                payload = json.dumps(message).encode('utf-8')

            # Gửi tin nhắn
            msg_info = self.client.publish(self.publish_topic, payload, qos=0)
            
            if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Gửi thành công batch {len(self.buffer)} điểm dữ liệu, kích thước payload: {len(payload)} bytes.")
            
            # Xử lý warning về unpublished messages với throttling
            if not msg_info.is_published():
                self._unpublished_mids.append(msg_info.mid)
                current_time = time.time()
                if current_time - self._last_warning_time > self._warning_log_delay:
                    mid_list = ", ".join(map(str, self._unpublished_mids[-10:]))  # Chỉ hiện 10 Mid gần nhất
                    count_msg = f" ({len(self._unpublished_mids)} batches)" if len(self._unpublished_mids) > 10 else ""
                    logger.warning(f"Tin nhắn batch có thể chưa được gửi (is_published=False). Recent Mids: {mid_list}{count_msg}")
                    self._last_warning_time = current_time
                    # Giữ lại chỉ 50 Mid gần nhất để tránh memory leak
                    if len(self._unpublished_mids) > 50:
                        self._unpublished_mids = self._unpublished_mids[-50:]

            # Xóa buffer sau khi gửi
            self.buffer.clear()
        except Exception as e:
            logger.error(f"Lỗi khi gửi dữ liệu batch: {e}")
            # Cân nhắc: Có nên xóa buffer nếu gửi lỗi? 
            # Giữ lại có thể gây ra buffer lớn, xóa đi sẽ mất dữ liệu.
            # Hiện tại, chọn giải pháp xóa để tránh tràn bộ nhớ.
            self.buffer.clear()

    def flush(self):
        """
        Gửi bất kỳ dữ liệu nào còn lại trong buffer.
        Hữu ích khi chương trình kết thúc.
        """
        logger.info(f"Flushing {len(self.buffer)} điểm dữ liệu còn lại trong buffer.")
        self.send_batch() 