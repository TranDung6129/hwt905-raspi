import logging
import logging.handlers
from pathlib import Path
import colorlog
from src.utils.common import ensure_directory_exists

class CustomColoredFormatter(colorlog.ColoredFormatter):
    """
    Formatter tùy chỉnh: tô màu cả dòng cho WARNING/ERROR,
    và chỉ tô màu level cho INFO/DEBUG.
    """
    def format(self, record):
        # Định dạng cho INFO và DEBUG (chỉ tô màu level)
        info_fmt = "%(asctime)s - %(name)s - [%(log_color)s%(levelname)s%(reset)s] - %(message)s"
        # Định dạng cho WARNING và cao hơn (tô màu cả dòng)
        warn_fmt = "%(log_color)s%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"

        # Thay đổi định dạng tạm thời dựa trên level
        if record.levelno >= logging.WARNING:
            self._style._fmt = warn_fmt
        else:
            self._style._fmt = info_fmt

        # Gọi formatter gốc để thực hiện việc tô màu
        return super().format(record)

def setup_logging(log_file_path: str, log_level: str, max_bytes: int = 10485760, backup_count: int = 5):
    """
    Thiết lập cấu hình logging cho ứng dụng.
    Log sẽ được ghi ra console (với màu sắc) và vào một file.

    Args:
        log_file_path (str): Đường dẫn đến file log.
        log_level (str): Cấp độ log (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR').
        max_bytes (int): Kích thước tối đa của file log trước khi nó được xoay vòng (bytes).
        backup_count (int): Số lượng file log cũ được giữ lại.
    """
    log_directory = Path(log_file_path).parent
    ensure_directory_exists(str(log_directory))

    logger = logging.getLogger()
    logger.setLevel(logging.getLevelName(log_level.upper()))

    # Xóa các handler cũ để tránh nhân đôi log
    if logger.hasHandlers():
        logger.handlers.clear()

    # Định dạng cho file log (không màu, không căn chỉnh)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Sử dụng Formatter tùy chỉnh cho console
    console_formatter = CustomColoredFormatter(
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'bold_red',
        }
    )

    # Handler cho console (sử dụng formatter tùy chỉnh)
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Handler cho file log
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.info(f"Logging đã được thiết lập thành công. Cấp độ: {log_level.upper()}, File: {log_file_path}")

# Giữ nguyên hàm setup_logger nếu nó vẫn được sử dụng ở đâu đó
def setup_logger(log_level: int = logging.INFO, name: str = None):
    """
    Thiết lập logger đơn giản cho service.
    
    Args:
        log_level: Cấp độ log (logging.INFO, logging.DEBUG, etc.)
        name: Tên logger (None để sử dụng root logger)
    """
    # Tạo hoặc lấy logger
    logger = logging.getLogger(name)
    
    # Xóa handlers cũ nếu có
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # Thiết lập level
    logger.setLevel(log_level)
    
    # Tạo formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Tạo console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Thêm handler
    logger.addHandler(console_handler)
    
    return logger