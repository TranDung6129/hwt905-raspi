# src/mqtt/scheduled_publisher.py
import logging
import time
import os
import glob
import threading
from typing import Dict, Any, List
from .base_publisher import BasePublisher
from src.utils.common import load_config
import paho.mqtt.client as mqtt
import copy
import json
import pandas as pd

logger = logging.getLogger(__name__)

class ScheduledPublisher(BasePublisher):
    """
    Publisher gửi dữ liệu theo lịch trình định kỳ.
    Đọc dữ liệu từ file lưu trữ và gửi đi theo batch.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Cấu hình scheduled
        scheduled_config = config.get("send_strategy", {})
        self.interval_seconds = scheduled_config.get("interval_seconds", 60)
        self.data_source_dir = scheduled_config.get("data_source_dir", "data/processed_data")
        self.batch_size = scheduled_config.get("batch_size", 100)
        self.delete_after_send = scheduled_config.get("delete_after_send", False)
        
        self.compressor = self.get_compressor()
        app_config = load_config()
        message_config = app_config.get('mqtt_message', {})
        self.message_template = message_config.get('message_templates', {}).get('scheduled', {}).get('structure', {})
        
        # Scheduled publisher sử dụng timer thread
        self._timer_thread = None
        self._running = False
        self._last_process_time = 0
        
        logger.info(f"Scheduled Publisher initialized:")
        logger.info(f"  Interval: {self.interval_seconds}s")
        logger.info(f"  Data source: {self.data_source_dir}")
        logger.info(f"  Batch size: {self.batch_size}")
        logger.info(f"  Delete after send: {self.delete_after_send}")

    def connect(self):
        """Kết nối và bắt đầu scheduler"""
        super().connect()
        self._start_scheduler()

    def disconnect(self):
        """Ngắt kết nối và dừng scheduler"""
        self._stop_scheduler()
        super().disconnect()

    def publish(self, data_point: Dict[str, Any]):
        """
        Scheduled publisher không nhận dữ liệu realtime.
        Thay vào đó, nó đọc dữ liệu từ file theo lịch trình.
        
        Args:
            data_point: Không sử dụng, chỉ để tương thích interface
        """
        logger.warning("ScheduledPublisher không hỗ trợ publish realtime data. Dữ liệu sẽ được đọc từ file theo lịch trình.")

    def _start_scheduler(self):
        """Bắt đầu timer thread để xử lý dữ liệu theo lịch trình"""
        if self._running:
            return
            
        self._running = True
        self._schedule_next_process()
        logger.info("Scheduled Publisher timer đã bắt đầu")

    def _stop_scheduler(self):
        """Dừng timer thread"""
        self._running = False
        if self._timer_thread:
            self._timer_thread.cancel()
        logger.info("Scheduled Publisher timer đã dừng")

    def _schedule_next_process(self):
        """Lên lịch cho lần xử lý tiếp theo"""
        if not self._running:
            return
            
        self._timer_thread = threading.Timer(self.interval_seconds, self._process_and_schedule)
        self._timer_thread.start()

    def _process_and_schedule(self):
        """Xử lý dữ liệu và lên lịch cho lần tiếp theo"""
        if not self._running:
            return
            
        try:
            self._process_data_files()
            self._last_process_time = time.time()
        except Exception as e:
            logger.error(f"Lỗi khi xử lý dữ liệu scheduled: {e}")
            
        # Lên lịch cho lần tiếp theo
        self._schedule_next_process()

    def _process_data_files(self):
        """Xử lý các file dữ liệu trong thư mục"""
        if not os.path.exists(self.data_source_dir):
            logger.warning(f"Thư mục dữ liệu không tồn tại: {self.data_source_dir}")
            return
            
        # Tìm tất cả file CSV trong thư mục
        csv_files = glob.glob(os.path.join(self.data_source_dir, "*.csv"))
        
        if not csv_files:
            logger.debug("Không có file dữ liệu để gửi")
            return
            
        logger.info(f"Tìm thấy {len(csv_files)} file dữ liệu để xử lý")
        
        for file_path in csv_files:
            try:
                self._process_single_file(file_path)
            except Exception as e:
                logger.error(f"Lỗi khi xử lý file {file_path}: {e}")

    def _process_single_file(self, file_path: str):
        """Xử lý một file dữ liệu"""
        logger.info(f"Xử lý file: {file_path}")
        
        try:
            # Đọc dữ liệu từ file CSV
            df = pd.read_csv(file_path)
            
            if df.empty:
                logger.warning(f"File {file_path} rỗng")
                if self.delete_after_send:
                    os.remove(file_path)
                return
                
            # Chuyển đổi dữ liệu thành format JSON
            data_points = []
            for _, row in df.iterrows():
                data_point = row.to_dict()
                # Xử lý NaN values
                for key, value in data_point.items():
                    if pd.isna(value):
                        data_point[key] = None
                data_points.append(data_point)
                
            # Gửi dữ liệu theo batch
            total_points = len(data_points)
            sent_count = 0
            
            for i in range(0, total_points, self.batch_size):
                batch = data_points[i:i + self.batch_size]
                
                # Tạo message từ template
                message = copy.deepcopy(self.message_template)
                message['metadata']['sample_count'] = len(batch)
                message['metadata']['start_time'] = batch[0].get('ts', 0) if batch else 0
                message['metadata']['end_time'] = batch[-1].get('ts', 0) if batch else 0
                message['metadata']['file_source'] = os.path.basename(file_path)
                message['metadata']['batch_info'] = {
                    'batch_number': i // self.batch_size + 1,
                    'total_batches': (total_points + self.batch_size - 1) // self.batch_size,
                    'points_in_batch': len(batch)
                }
                message['data_points'] = batch
                
                # Gửi batch
                try:
                    if self.compressor:
                        payload = self.compressor.compress(message)
                    else:
                        payload = json.dumps(message).encode('utf-8')
                        
                    msg_info = self.client.publish(self.publish_topic, payload, qos=0)
                    
                    if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                        sent_count += len(batch)
                        logger.debug(f"Gửi thành công batch {i // self.batch_size + 1}/{(total_points + self.batch_size - 1) // self.batch_size}")
                    else:
                        logger.error(f"Lỗi gửi batch: {msg_info.rc}")
                        
                except Exception as e:
                    logger.error(f"Lỗi khi gửi batch từ file {file_path}: {e}")
                    
            logger.info(f"Đã gửi {sent_count}/{total_points} điểm dữ liệu từ {file_path}")
            
            # Xóa file sau khi gửi thành công (nếu được cấu hình)
            if self.delete_after_send and sent_count == total_points:
                os.remove(file_path)
                logger.info(f"Đã xóa file {file_path}")
                
        except Exception as e:
            logger.error(f"Lỗi khi xử lý file {file_path}: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái của scheduled publisher"""
        return {
            'running': self._running,
            'last_process_time': self._last_process_time,
            'interval_seconds': self.interval_seconds,
            'data_source_dir': self.data_source_dir,
            'batch_size': self.batch_size,
            'delete_after_send': self.delete_after_send
        }
