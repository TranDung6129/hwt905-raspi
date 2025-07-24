#!/bin/bash

# Cài đặt và khởi động HWT905 Raspberry Pi IMU Data Processing Service
# Hỗ trợ 3 chế độ: realtime, batch, scheduled

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_DIR="$PROJECT_DIR/systemd"

# Màu sắc cho output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Kiểm tra quyền sudo
if [[ $EUID -ne 0 ]]; then
    print_error "Script này cần chạy với quyền sudo"
    exit 1
fi

# Hiển thị menu lựa chọn
echo "=== HWT905 Raspberry Pi IMU Service Installer ==="
echo "Chọn chế độ hoạt động:"
echo "1) Realtime Mode - Gửi dữ liệu ngay lập tức"
echo "2) Batch Mode - Gửi dữ liệu theo batch"
echo "3) Scheduled Mode - Gửi dữ liệu theo lịch trình"
echo "4) Cài đặt tất cả (không bật tự động)"
echo "5) Gỡ bỏ tất cả service"
echo

read -p "Nhập lựa chọn của bạn (1-5): " choice

case $choice in
    1)
        SERVICE_NAME="hwt905-raspi"
        SERVICE_FILE="hwt905-raspi.service"
        MODE="realtime"
        ;;
    2)
        SERVICE_NAME="hwt905-raspi-batch"
        SERVICE_FILE="hwt905-raspi-batch.service"
        MODE="batch"
        ;;
    3)
        SERVICE_NAME="hwt905-raspi-scheduled"
        SERVICE_FILE="hwt905-raspi-scheduled.service"
        MODE="scheduled"
        ;;
    4)
        # Cài đặt tất cả
        print_info "Cài đặt tất cả service files..."
        cp "$SERVICE_DIR/hwt905-raspi.service" /etc/systemd/system/
        cp "$SERVICE_DIR/hwt905-raspi-batch.service" /etc/systemd/system/
        cp "$SERVICE_DIR/hwt905-raspi-scheduled.service" /etc/systemd/system/
        
        systemctl daemon-reload
        
        print_info "Đã cài đặt tất cả service files:"
        print_info "- hwt905-raspi.service (realtime mode)"
        print_info "- hwt905-raspi-batch.service (batch mode)"
        print_info "- hwt905-raspi-scheduled.service (scheduled mode)"
        print_info ""
        print_info "Để bật và khởi động service, chạy:"
        print_info "sudo systemctl enable --now hwt905-raspi         # Cho realtime mode"
        print_info "sudo systemctl enable --now hwt905-raspi-batch   # Cho batch mode"
        print_info "sudo systemctl enable --now hwt905-raspi-scheduled # Cho scheduled mode"
        exit 0
        ;;
    5)
        # Gỡ bỏ tất cả
        print_info "Dừng và gỡ bỏ tất cả service..."
        
        for service in hwt905-raspi hwt905-raspi-batch hwt905-raspi-scheduled; do
            if systemctl is-active --quiet $service; then
                print_info "Dừng service $service..."
                systemctl stop $service
            fi
            
            if systemctl is-enabled --quiet $service; then
                print_info "Vô hiệu hóa service $service..."
                systemctl disable $service
            fi
            
            if [ -f "/etc/systemd/system/$service.service" ]; then
                print_info "Xóa file service $service.service..."
                rm -f "/etc/systemd/system/$service.service"
            fi
        done
        
        systemctl daemon-reload
        print_info "Đã gỡ bỏ tất cả service thành công!"
        exit 0
        ;;
    *)
        print_error "Lựa chọn không hợp lệ"
        exit 1
        ;;
esac

print_info "Cài đặt service cho chế độ $MODE..."

# Kiểm tra file service tồn tại
if [ ! -f "$SERVICE_DIR/$SERVICE_FILE" ]; then
    print_error "File service $SERVICE_FILE không tồn tại trong $SERVICE_DIR"
    exit 1
fi

# Dừng service hiện tại nếu đang chạy
if systemctl is-active --quiet $SERVICE_NAME; then
    print_info "Dừng service $SERVICE_NAME..."
    systemctl stop $SERVICE_NAME
fi

# Copy service file
print_info "Copy service file..."
cp "$SERVICE_DIR/$SERVICE_FILE" /etc/systemd/system/

# Reload systemd
print_info "Reload systemd daemon..."
systemctl daemon-reload

# Enable và start service
print_info "Enable và start service..."
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Kiểm tra trạng thái
sleep 2
if systemctl is-active --quiet $SERVICE_NAME; then
    print_info "Service $SERVICE_NAME đã được cài đặt và khởi động thành công!"
    print_info "Để kiểm tra trạng thái: sudo systemctl status $SERVICE_NAME"
    print_info "Để xem log: sudo journalctl -u $SERVICE_NAME -f"
else
    print_error "Service $SERVICE_NAME không thể khởi động. Kiểm tra log để biết chi tiết:"
    print_error "sudo journalctl -u $SERVICE_NAME -n 20"
    exit 1
fi

print_info "Cài đặt hoàn tất!"

