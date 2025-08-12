# CoinJoin Address Groups - Hướng dẫn sử dụng

## Tổng quan

Màn hình **CoinJoin Address Groups** cho phép bạn phân tích và hiển thị các nhóm địa chỉ liên quan đến giao dịch CoinJoin. Đây là một công cụ mạnh mẽ để hiểu rõ bản chất của các giao dịch CoinJoin và cách các địa chỉ được tổ chức thành các nhóm.

## Tính năng chính

### 1. Hiển thị nhóm địa chỉ CoinJoin
- **Tự động phân tích**: Hệ thống tự động phát hiện các giao dịch CoinJoin và nhóm các địa chỉ liên quan
- **Thống kê chi tiết**: Hiển thị số lượng địa chỉ input/output, tổng số dư, thời gian giao dịch
- **Phân loại địa chỉ**: Tự động phân loại địa chỉ theo cluster và tags

### 2. Chọn và xem chi tiết
- **Chọn nhiều nhóm**: Click vào các nhóm để chọn (có thể chọn nhiều nhóm cùng lúc)
- **Xem đồ thị**: Nút "Xem chi tiết đồ thị" để hiển thị mối quan hệ giữa các địa chỉ
- **Modal đồ thị**: Hiển thị đồ thị tương tác trong modal toàn màn hình

### 3. Đồ thị tương tác
- **Biểu diễn rẽ nhánh**: Đồ thị hiển thị dạng rẽ nhánh từ ngọn và hợp nhất về gốc
- **Màu sắc phân loại**: Các địa chỉ được phân loại bằng màu sắc khác nhau
- **Thông tin chi tiết**: Hover để xem thông tin chi tiết của từng node

## Cách sử dụng

### Bước 1: Truy cập màn hình
1. Vào menu sidebar
2. Chọn "CoinJoin Address Groups"
3. Hoặc truy cập trực tiếp: `/bitcoin/coinjoin-groups/`

### Bước 2: Xem danh sách nhóm
- Màn hình sẽ hiển thị các thống kê tổng quan:
  - Tổng số nhóm
  - Số giao dịch CoinJoin
  - Tổng số địa chỉ liên quan
  - Số nhóm đã chọn

### Bước 3: Chọn nhóm để phân tích
- Click vào các card nhóm để chọn (có thể chọn nhiều nhóm)
- Card được chọn sẽ có viền màu xanh và background nhạt
- Số lượng nhóm đã chọn sẽ hiển thị ở thống kê

### Bước 4: Xem đồ thị chi tiết
- Click nút "🔍 Xem chi tiết đồ thị"
- Modal sẽ mở ra với thông tin các địa chỉ đã chọn
- Đồ thị sẽ được tải và hiển thị

### Bước 5: Tương tác với đồ thị
- **Zoom**: Sử dụng chuột để zoom in/out
- **Pan**: Kéo để di chuyển đồ thị
- **Click node**: Click vào node để xem thông tin chi tiết
- **Navigation**: Sử dụng các nút điều hướng

## Cấu trúc dữ liệu

### Models được sử dụng
- **Transaction**: Giao dịch chính
- **TxInput**: Đầu vào của giao dịch
- **TxOutput**: Đầu ra của giao dịch (UTXO)
- **Address**: Địa chỉ Bitcoin
- **AddressCluster**: Cụm địa chỉ

### API Endpoints
- `GET /bitcoin/api/coinjoin-groups/`: Lấy danh sách nhóm
- `POST /bitcoin/api/coinjoin-groups/graph/`: Lấy dữ liệu đồ thị

## Thuật toán phân tích

### 1. Phát hiện CoinJoin
- Sử dụng `AdvancedCoinJoinDetector` để phân tích
- Kiểm tra các tiêu chí:
  - Số lượng input/output cao (≥10)
  - Độ đồng đều của giá trị output
  - Phân tích đệ quy các giao dịch liên quan

### 2. Nhóm địa chỉ
- Tự động nhóm các địa chỉ theo cluster
- Phân tích mối quan hệ giữa các địa chỉ
- Tính toán số dư và thống kê

### 3. Xây dựng đồ thị
- Tạo nodes cho địa chỉ và giao dịch
- Tạo edges thể hiện mối quan hệ
- Áp dụng thuật toán layout để hiển thị

## Lưu ý kỹ thuật

### Performance
- Giới hạn 100 giao dịch CoinJoin để phân tích
- Sử dụng prefetch_related để tối ưu query
- Caching kết quả phân tích

### Bảo mật
- CSRF protection cho các API POST
- Validation dữ liệu đầu vào
- Error handling cho các trường hợp ngoại lệ

### Responsive Design
- Tương thích với mobile và desktop
- Modal toàn màn hình cho đồ thị
- Loading states và error handling

## Troubleshooting

### Lỗi thường gặp
1. **Không có dữ liệu**: Kiểm tra xem có giao dịch CoinJoin trong database không
2. **Đồ thị không hiển thị**: Kiểm tra console để xem lỗi JavaScript
3. **API error**: Kiểm tra logs server để xem lỗi backend

### Debug
- Sử dụng browser developer tools
- Kiểm tra Network tab để xem API calls
- Xem Console tab để debug JavaScript

## Tương lai

### Tính năng dự kiến
- Export dữ liệu đồ thị
- Lưu và chia sẻ phân tích
- Real-time updates
- Advanced filtering options
- Batch analysis

### Cải tiến
- Tối ưu performance cho dataset lớn
- Thêm các thuật toán phân tích nâng cao
- UI/UX improvements
- Mobile app support 