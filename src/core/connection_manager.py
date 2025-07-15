import logging
import time
import serial
import glob
from typing import Optional, List

from src.sensors.config.unified_config_manager import HWT905UnifiedConfigManager
from src.sensors.hwt905_constants import (
    BAUD_RATE_9600, BAUD_RATE_115200, BAUD_RATE_460800, BAUD_RATE_921600
)

logger = logging.getLogger(__name__)

class SensorConnectionManager:
    """
    Quản lý kết nối, cấu hình và tái kết nối với cảm biến HWT905.
    """

    def __init__(self, sensor_config: dict, debug: bool = False):
        """
        Khởi tạo ConnectionManager.

        Args:
            sensor_config (dict): Dictionary cấu hình cảm biến từ app_config.json.
            debug (bool): Bật chế độ debug.
        """
        self.port_pattern = sensor_config.get("uart_port_pattern", "/dev/ttyUSB*")
        self.target_baudrate_val = sensor_config.get("baud_rate", 115200)
        self.reconnect_delay_s = sensor_config.get("reconnect_delay_s", 5)
        self.debug = debug
        
        # Các baudrate phổ biến để thử nếu kết nối thất bại
        self.baudrate_candidates = [
            self.target_baudrate_val,
            BAUD_RATE_115200,
            BAUD_RATE_9600,
            BAUD_RATE_460800,
            BAUD_RATE_921600
        ]
        
        self.ser: Optional[serial.Serial] = None
        self.config_manager: Optional[HWT905UnifiedConfigManager] = None

    def _find_available_ports(self) -> List[str]:
        """Tìm và trả về danh sách các cổng serial phù hợp với pattern."""
        ports = glob.glob(self.port_pattern)
        if not ports:
            logger.warning(f"Không tìm thấy cổng nào khớp với mẫu: {self.port_pattern}")
        else:
            logger.info(f"Đã tìm thấy các cổng tiềm năng: {ports}")
        return sorted(ports)

    def establish_connection(self) -> Optional[serial.Serial]:
        """
        Quét các cổng có sẵn và cố gắng thiết lập kết nối, thử các baudrate khác nhau.
        Hàm này sẽ lặp lại cho đến khi kết nối thành công hoặc bị ngắt.

        Returns:
            Một instance serial.Serial đã kết nối thành công, hoặc None nếu không thể.
        """
        while True: # Vòng lặp này sẽ chạy cho đến khi kết nối được thiết lập
            available_ports = self._find_available_ports()
            if not available_ports:
                logger.error(f"Không có cổng serial nào. Sẽ thử lại sau {self.reconnect_delay_s} giây.")
                time.sleep(self.reconnect_delay_s)
                continue

            for port in available_ports:
                logger.info(f"Đang thử kết nối trên cổng {port}...")
                
                # Cố gắng kết nối với các baudrate khác nhau
                for baud in self.baudrate_candidates:
                    logger.debug(f"Thử {port} với baudrate: {baud}...")
                    try:
                        temp_ser = serial.Serial(port, baud, timeout=0.1)
                        
                        # Tạo một config_manager tạm thời để xác minh kết nối
                        temp_cfg_manager = HWT905UnifiedConfigManager(
                            port=port, baudrate=baud, debug=self.debug
                        )
                        temp_cfg_manager.set_ser_instance(temp_ser)

                        # Xác minh xem có thể giao tiếp ở baudrate này không
                        if temp_cfg_manager.verify_baudrate():
                            logger.info(f"Kết nối thành công với cảm biến tại {port} @ {baud} bps.")
                            self.port = port # Cập nhật lại cổng đã kết nối thành công
                            self.ser = temp_ser
                            self.config_manager = temp_cfg_manager
                            return self.ser
                        else:
                            logger.debug(f"Không nhận được phản hồi hợp lệ tại {baud} bps trên {port}.")
                            temp_ser.close()
                            
                    except serial.SerialException as e:
                        logger.warning(f"Không thể mở cổng {port} tại {baud} bps: {e}")
                        # Lỗi này thường có nghĩa là cổng đang được sử dụng hoặc không tồn tại nữa
                        # Chuyển sang thử cổng tiếp theo
                        break 
                    except Exception as e:
                        logger.error(f"Lỗi không xác định khi thử kết nối trên {port}: {e}")
                        if 'temp_ser' in locals() and temp_ser.is_open:
                            temp_ser.close()

            logger.error(f"Không tìm thấy cảm biến trên bất kỳ cổng nào. "
                         f"Sẽ quét lại sau {self.reconnect_delay_s} giây.")
            time.sleep(self.reconnect_delay_s)
            
    def get_serial_instance(self) -> Optional[serial.Serial]:
        return self.ser

    def get_config_manager(self) -> Optional[HWT905UnifiedConfigManager]:
        return self.config_manager

    def close_connection(self):
        """Đóng kết nối serial nếu đang mở."""
        if self.config_manager:
            self.config_manager.close()
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"Đã đóng kết nối trên cổng {self.port}.")
        self.ser = None
        self.config_manager = None

    def ensure_correct_config(self) -> bool:
        """
        Đảm bảo cảm biến được cấu hình với baudrate mục tiêu.
        Nếu baudrate hiện tại không đúng, hàm sẽ cố gắng đặt lại nó.
        """
        if not self.config_manager or not self.ser:
            logger.error("Không thể cấu hình cảm biến: chưa có kết nối.")
            return False

        current_baud = self.ser.baudrate
        if current_baud == self.target_baudrate_val:
            logger.info(f"Baudrate của cảm biến đã đúng ({self.target_baudrate_val} bps).")
            return True

        logger.warning(f"Baudrate hiện tại ({current_baud}) khác với mục tiêu ({self.target_baudrate_val}). "
                       f"Đang cố gắng cấu hình lại.")
        
        # Ánh xạ giá trị baudrate sang hằng số của cảm biến
        baud_const_map = {
            9600: BAUD_RATE_9600,
            115200: BAUD_RATE_115200,
            460800: BAUD_RATE_460800,
            921600: BAUD_RATE_921600,
        }
        target_baud_const = baud_const_map.get(self.target_baudrate_val)
        
        if not target_baud_const:
            logger.error(f"Baudrate mục tiêu {self.target_baudrate_val} không được hỗ trợ để cấu hình.")
            return False

        if self.config_manager.unlock_sensor_for_config():
            if self.config_manager.set_baudrate(target_baud_const):
                if self.config_manager.save_configuration():
                    logger.info(f"Đã gửi lệnh đổi baudrate sang {self.target_baudrate_val}. "
                                f"Cần phải kết nối lại với baudrate mới.")
                    # Đóng kết nối hiện tại để vòng lặp chính có thể kết nối lại
                    self.close_connection()
                    return False # Trả về False để báo hiệu cần kết nối lại
            else:
                logger.error("Không thể gửi lệnh set_baudrate.")
        else:
            logger.error("Không thể mở khóa cảm biến để cấu hình.")

        logger.critical("Không thể cấu hình lại baudrate. Cảm biến có thể vẫn hoạt động ở baudrate cũ.")
        return False 