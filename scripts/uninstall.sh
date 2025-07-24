#!/bin/bash

# Gỡ bỏ HWT905 Raspberry Pi IMU Data Processing Service

set -e

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

echo "=== HWT905 Raspberry Pi IMU Service Uninstaller ==="
echo

# Danh sách các service
services=("hwt905-raspi" "hwt905-raspi-batch" "hwt905-raspi-scheduled")

print_info "Đang kiểm tra và gỡ bỏ các service..."

for service in "${services[@]}"; do
    print_info "Xử lý service: $service"
    
    # Dừng service nếu đang chạy
    if systemctl is-active --quiet "$service"; then
        print_info "Dừng service $service..."
        systemctl stop "$service"
    else
        print_info "Service $service không đang chạy"
    fi
    
    # Vô hiệu hóa service nếu được enable
    if systemctl is-enabled --quiet "$service" 2>/dev/null; then
        print_info "Vô hiệu hóa service $service..."
        systemctl disable "$service"
    else
        print_info "Service $service không được enable"
    fi
    
    # Xóa file service
    if [ -f "/etc/systemd/system/$service.service" ]; then
        print_info "Xóa file service $service.service..."
        rm -f "/etc/systemd/system/$service.service"
    else
        print_info "File service $service.service không tồn tại"
    fi
    
    echo
done

# Reload systemd daemon
print_info "Reload systemd daemon..."
systemctl daemon-reload

print_info "Đã gỡ bỏ tất cả HWT905 service thành công!"
print_info ""
print_info "Để xóa hoàn toàn ứng dụng, bạn có thể:"
print_info "1. Xóa thư mục project"
print_info "2. Xóa user và group nếu được tạo riêng"
print_info "3. Xóa log files trong /var/log (nếu có)"
print_info ""
print_info "Gỡ bỏ hoàn tất!"
