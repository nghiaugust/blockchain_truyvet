# CoinJoin Address Selector - Hướng Dẫn Sử Dụng

## Tổng Quan

CoinJoin Address Selector là một tính năng cho phép bạn chọn và phân tích các địa chỉ Bitcoin liên quan đến giao dịch CoinJoin. Tính năng này sử dụng logic phát hiện CoinJoin cải tiến với đệ quy và ma trận cây địa chỉ.

## Tính Năng Chính

### 🎯 **Chọn Địa Chỉ**
- Hiển thị tất cả địa chỉ liên quan đến giao dịch CoinJoin
- Chọn nhiều địa chỉ cùng lúc
- Tìm kiếm địa chỉ theo từ khóa
- Chọn/bỏ chọn tất cả địa chỉ

### 📊 **Hiển Thị Dạng Bảng**
- Layout grid responsive từ trái sang phải
- Mỗi địa chỉ hiển thị trong một card riêng
- Màu sắc phân biệt theo tags
- Thông tin chi tiết: số giao dịch, cluster size, tags

### 🔍 **Phân Tích Chi Tiết**
- Xem số dư của địa chỉ
- Danh sách giao dịch liên quan
- Thông tin anomaly score
- Tags và phân loại

## Cách Sử Dụng

### 1. **Truy Cập Trang**
```
URL: /bitcoin/coinjoin-selector/
Hoặc click vào "CoinJoin Address Selector" trên trang chính
```

### 2. **Chọn Địa Chỉ**
- Click vào card địa chỉ để chọn/bỏ chọn
- Sử dụng "Chọn Tất Cả" để chọn tất cả
- Sử dụng "Bỏ Chọn Tất Cả" để bỏ chọn tất cả
- Tìm kiếm bằng ô tìm kiếm

### 3. **Xem Chi Tiết**
- Chọn ít nhất một địa chỉ
- Click "Xem Chi Tiết" để mở modal
- Xem thông tin chi tiết và giao dịch liên quan

## Giao Diện

### **Header Section**
- Thống kê tổng quan: số địa chỉ, số giao dịch, số đã chọn
- Mô tả tính năng

### **Selection Controls**
- Ô tìm kiếm địa chỉ
- Nút chọn/bỏ chọn tất cả
- Nút xem chi tiết

### **Address Grid**
- Hiển thị dạng grid responsive
- Mỗi card chứa thông tin địa chỉ
- Màu sắc theo tags:
  - 🔴 Đỏ: CoinJoin
  - 🟣 Tím: Clustered
  - 🟢 Xanh lá: High reuse
  - 🔵 Xanh dương: Reuse
  - 🟡 Vàng: New

### **Modal Chi Tiết**
- Thông tin địa chỉ: số dư, số giao dịch, tags
- Bảng giao dịch liên quan
- Badge CoinJoin cho giao dịch CoinJoin

## Dữ Liệu Hiển Thị

### **Thông Tin Địa Chỉ**
```json
{
  "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "balance": 0.00123456,
  "tx_count": 15,
  "tags": "coinjoin,clustered,high_reuse",
  "color": "#FF6B6B",
  "input_txs": ["tx_hash_1", "tx_hash_2"],
  "output_txs": ["tx_hash_3", "tx_hash_4"],
  "cluster_id": ["addr1", "addr2", "addr3"]
}
```

### **Thông Tin Giao Dịch**
```json
{
  "hash": "abc123...",
  "time": "2024-01-01 12:00:00",
  "fee": 1000,
  "tags": "coinjoin,high_io",
  "anomaly_score": 3.5,
  "is_coinjoin": true
}
```

## Logic Phát Hiện CoinJoin

### **Tiêu Chí Cơ Bản**
- ≥ 10 inputs và ≥ 10 outputs
- Độ đồng đều giá trị đầu ra (±5%)
- Đa dạng địa chỉ input

### **Phân Tích Nâng Cao**
- Đệ quy theo dõi giao dịch liên quan
- Ma trận cây địa chỉ
- Confidence scoring kết hợp

### **Tags Phân Loại**
- `coinjoin`: Địa chỉ tham gia CoinJoin
- `clustered`: Địa chỉ trong cùng cluster
- `high_reuse`: Địa chỉ tái sử dụng nhiều
- `reuse`: Địa chỉ tái sử dụng
- `new`: Địa chỉ mới

## Test và Demo

### **Tạo Dữ Liệu Mẫu**
```bash
python manage.py test_coinjoin_selector --create-sample
```

### **Kiểm Tra Dữ Liệu**
```bash
python manage.py test_coinjoin_selector --check-data
```

### **Chạy Enhanced Heuristics**
```bash
python manage.py enhanced_heuristics --enable-advanced-coinjoin
```

## API Endpoints

### **GET /bitcoin/coinjoin-selector/**
- Hiển thị trang chọn địa chỉ CoinJoin

### **POST /bitcoin/api/coinjoin-addresses/data/**
- Lấy thông tin chi tiết địa chỉ đã chọn
- Body: `{"addresses": ["addr1", "addr2"]}`
- Response: Thông tin chi tiết các địa chỉ

## Cấu Hình

### **Số Lượng Hiển Thị**
- Mặc định: 100 giao dịch CoinJoin gần nhất
- Có thể điều chỉnh trong view

### **Grid Layout**
- Responsive: tự động điều chỉnh theo màn hình
- Mobile: 1 cột
- Tablet: 2-3 cột
- Desktop: 4+ cột

### **Search Functionality**
- Tìm kiếm theo địa chỉ
- Real-time filtering
- Case-insensitive

## Troubleshooting

### **Không Hiển Thị Địa Chỉ**
1. Kiểm tra có giao dịch CoinJoin trong database
2. Chạy enhanced heuristics để phát hiện CoinJoin
3. Kiểm tra logs để debug

### **Modal Không Mở**
1. Kiểm tra JavaScript console
2. Đảm bảo đã chọn ít nhất một địa chỉ
3. Kiểm tra CSRF token

### **Performance Chậm**
1. Giảm số lượng giao dịch hiển thị
2. Thêm index cho database
3. Sử dụng caching

## Tương Lai Phát Triển

### **Tính Năng Mới**
- Export dữ liệu đã chọn
- Filter theo tags
- Sort theo các tiêu chí
- Batch operations

### **Cải Tiến UI/UX**
- Drag & drop selection
- Keyboard shortcuts
- Advanced filtering
- Real-time updates

### **Tích Hợp**
- Graph visualization
- Transaction flow analysis
- Address clustering view
- Export to CSV/JSON

## Liên Kết

- [Advanced CoinJoin Detection](./ADVANCED_COINJOIN_DETECTION.md)
- [Enhanced Heuristics](./blockchain/bitcoin/management/commands/enhanced_heuristics.py)
- [Address Tree Logic](./blockchain/bitcoin/management/commands/advanced_coinjoin.py) 