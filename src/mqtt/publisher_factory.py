# src/mqtt/publisher_factory.py
import logging
from typing import Dict, Any, Optional
from .base_publisher import BasePublisher
from .realtime_publisher import RealtimePublisher
from .batch_publisher import BatchPublisher
from .scheduled_publisher import ScheduledPublisher
from src.utils.common import load_config

logger = logging.getLogger(__name__)

def get_publisher(mode: str = None) -> Optional[BasePublisher]:
    """
    Factory function để tạo và trả về một instance của publisher phù hợp.

    Đọc file cấu hình, xác định chiến lược gửi tin (send_strategy) 
    và khởi tạo lớp publisher tương ứng.

    Args:
        mode (str): Chế độ gửi dữ liệu ('continuous', 'batch', 'scheduled')
                   Nếu None, sử dụng cấu hình từ file config.

    Returns:
        Optional[BasePublisher]: Một instance của publisher hoặc None nếu có lỗi.
    """
    try:
        app_config = load_config()  # Sử dụng hệ thống cấu hình mới
        mqtt_config = app_config.get('mqtt', {})
        strategy_config = mqtt_config.get('send_strategy', {})
        
        # Xác định strategy type từ mode parameter hoặc config
        if mode:
            if mode == 'continuous':
                strategy_type = 'realtime'
            elif mode == 'batch':
                strategy_type = 'batch'
            elif mode == 'scheduled':
                strategy_type = 'scheduled'
            else:
                logger.error(f"Mode không hợp lệ: '{mode}'. Vui lòng chọn 'continuous', 'batch', hoặc 'scheduled'.")
                return None
        else:
            strategy_type = strategy_config.get('type', 'realtime') # Mặc định là realtime

        logger.info(f"Đang khởi tạo MQTT publisher với chiến lược: '{strategy_type}' (mode: {mode})")

        if strategy_type == 'realtime':
            return RealtimePublisher(config=mqtt_config)
        elif strategy_type == 'batch':
            return BatchPublisher(config=mqtt_config)
        elif strategy_type == 'scheduled':
            return ScheduledPublisher(config=mqtt_config)
        else:
            logger.error(f"Chiến lược gửi MQTT không hợp lệ: '{strategy_type}'. Vui lòng chọn 'realtime', 'batch', hoặc 'scheduled'.")
            return None
            
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo publisher: {e}")
        return None 