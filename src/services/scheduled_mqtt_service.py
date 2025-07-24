# src/services/scheduled_mqtt_service.py
import logging
import threading
import time
import os
import glob
from typing import Dict, Any
from src.mqtt.publisher_factory import get_publisher
from src.mqtt.batch_publisher import BatchPublisher
from src.utils.common import load_config
import json
import pandas as pd

logger = logging.getLogger(__name__)

class ScheduledMqttService:
    """
    Service gửi dữ liệu MQTT theo lịch trình định kỳ.
    Đọc dữ liệu đã lưu trong thư mục và gửi đi theo batch.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.interval_seconds = config.get('interval_seconds', 60)
        self.data_source_dir = config.get('data_source_dir', 'data/processed_data')
        self.batch_size = config.get('batch_size', 100)
        self.delete_after_send = config.get('delete_after_send', False)
        self.topic = config.get('topic', 'sensor/scheduled_data')
        
        self.running = False
        self.thread = None
        self.publisher = None
        
        logger.info(f"Scheduled MQTT Service initialized:")
        logger.info(f"  Interval: {self.interval_seconds}s")
        logger.info(f"  Data source: {self.data_source_dir}")
        logger.info(f"  Batch size: {self.batch_size}")
        logger.info(f"  Delete after send: {self.delete_after_send}")
        
    def start(self):
        """Khởi động service"""
        if self.running:
            logger.warning("Scheduled MQTT Service đã đang chạy")
            return
            
        logger.info("Khởi động Scheduled MQTT Service...")
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Dừng service"""
        logger.info("Dừng Scheduled MQTT Service...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            
        if self.publisher:
            self.publisher.disconnect()
            
        logger.info("Scheduled MQTT Service đã dừng")
        
    def _run_loop(self):
        """Vòng lặp chính của service"""
        logger.info("Scheduled MQTT Service thread đã bắt đầu")
        
        # Khởi tạo publisher
        try:
            app_config = load_config()
            mqtt_config = app_config.get('mqtt', {})
            # Tạo BatchPublisher để gửi dữ liệu theo batch
            self.publisher = BatchPublisher(config=mqtt_config)
            self.publisher.connect()
            logger.info("Đã kết nối tới MQTT broker")
        except Exception as e:
            logger.error(f"Không thể khởi tạo publisher: {e}")
            return
            
        while self.running:
            try:
                self._process_data_files()
                time.sleep(self.interval_seconds)
            except Exception as e:
                logger.error(f"Lỗi trong vòng lặp scheduled service: {e}")
                time.sleep(5)  # Ngủ ngắn trước khi thử lại
                
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
                
                # Tạo message theo format batch
                message = {
                    'metadata': {
                        'device_id': 'hwt905-raspi',
                        'message_type': 'scheduled_batch',
                        'timestamp': int(time.time()),
                        'file_source': os.path.basename(file_path),
                        'batch_info': {
                            'batch_number': i // self.batch_size + 1,
                            'total_batches': (total_points + self.batch_size - 1) // self.batch_size,
                            'points_in_batch': len(batch)
                        }
                    },
                    'data_points': batch
                }
                
                # Gửi batch
                if self.publisher:
                    payload = json.dumps(message).encode('utf-8')
                    self.publisher.client.publish(self.topic, payload)
                    sent_count += len(batch)
                    
            logger.info(f"Đã gửi {sent_count}/{total_points} điểm dữ liệu từ {file_path}")
            
            # Xóa file sau khi gửi thành công (nếu được cấu hình)
            if self.delete_after_send:
                os.remove(file_path)
                logger.info(f"Đã xóa file {file_path}")
                
        except Exception as e:
            logger.error(f"Lỗi khi xử lý file {file_path}: {e}")
            raise


class ScheduledMqttServiceManager:
    """Manager để quản lý ScheduledMqttService"""
    
    def __init__(self):
        self.service = None
        
    def initialize(self, config: Dict[str, Any]):
        """Khởi tạo service với config"""
        self.service = ScheduledMqttService(config)
        
    def start(self):
        """Khởi động service"""
        if self.service:
            self.service.start()
            
    def stop(self):
        """Dừng service"""
        if self.service:
            self.service.stop()


# Global instance
scheduled_mqtt_manager = ScheduledMqttServiceManager()
