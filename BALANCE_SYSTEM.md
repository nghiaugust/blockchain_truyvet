# Hệ Thống Tính Số Dư Ví Bitcoin

## Tổng Quan

Hệ thống này cho phép tự động tính số dư của địa chỉ ví Bitcoin dựa trên dữ liệu giao dịch có sẵn trong database.

## Cách Hoạt Động

### 1. **Khi Thêm Địa Chỉ Ví Mới**

- Người dùng nhập địa chỉ Bitcoin
- Hệ thống tự động tìm địa chỉ đó trong bảng `bitcoin_address`
- Tính tổng các UTXO (outputs chưa được spend)
- Lưu số dư vào trường `balance` của `WalletAddress`

### 2. **Công Thức Tính Số Dư**

```python
# Tìm tất cả outputs của địa chỉ mà is_spent=False
unspent_outputs = TxOutput.objects.filter(
    address=address_obj,
    is_spent=False
).aggregate(total=Sum('value'))['total'] or 0

# Chuyển từ satoshi sang BTC
balance_btc = unspent_outputs / 100000000
```

### 3. **Database Schema**

#### Bảng `user_wallet_address`:

- `balance`: DecimalField(max_digits=16, decimal_places=8) - Số dư BTC

#### Bảng `bitcoin_txoutput`:

- `value`: BigIntegerField - Giá trị output (satoshi)
- `is_spent`: BooleanField - Đã được spend chưa
- `address`: ForeignKey to Address

## Sử Dụng

### 1. **Thêm Địa Chỉ Ví (Tự Động Tính Số Dư)**

```javascript
// POST /user/wallet/add-address/
{
    "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "label": "Ví chính",
    "address_type": "P2PKH",
    "is_primary": true
}
```

Hệ thống sẽ:

1. Validate địa chỉ
2. Tìm trong database Bitcoin
3. Tính số dư từ UTXO
4. Lưu vào database với số dư đã tính

### 2. **Cập Nhật Số Dư Thủ Công**

```javascript
// POST /user/wallet/refresh-balance/{address_id}/
```

Response:

```json
{
  "success": true,
  "message": "Cập nhật số dư thành công",
  "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "old_balance": "0.50000000",
  "new_balance": "0.75000000",
  "difference": "0.25000000"
}
```

### 3. **Xem Ví (Với Tùy Chọn Cập Nhật)**

```
GET /user/wallet/?update_balance=true
```

## Test và Debug

### 1. **Chạy Script Test**

```bash
cd blockchain/
python manage.py shell < ../test_balance.py
```

### 2. **Kiểm tra Manual**

```python
# Trong Django shell
from user.models import WalletAddress
from user.views import calculate_address_balance

# Test địa chỉ cụ thể
balance = calculate_address_balance("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
print(f"Số dư: {balance} BTC")
```

### 3. **Kiểm tra Database**

```sql
-- Xem addresses có UTXO
SELECT a.address, COUNT(o.id) as utxo_count, SUM(o.value) as total_value
FROM bitcoin_address a
JOIN bitcoin_txoutput o ON o.address_id = a.address
WHERE o.is_spent = FALSE
GROUP BY a.address
LIMIT 10;

-- Xem wallet addresses và số dư
SELECT u.username, wa.address, wa.label, wa.balance
FROM user_walletaddress wa
JOIN auth_user u ON u.id = wa.user_id
WHERE wa.is_active = TRUE;
```

## Lưu Ý Quan Trọng

### 1. **Dữ Liệu Phụ Thuộc**

- Cần có dữ liệu trong bảng `bitcoin_address`
- Cần có dữ liệu trong bảng `bitcoin_txoutput` với `is_spent` được cập nhật chính xác

### 2. **Performance**

- Sử dụng database indexes trên `address` và `is_spent`
- Tính số dư chỉ khi cần thiết (khi thêm địa chỉ hoặc user yêu cầu)

### 3. **Độ Chính Xác**

- Số dư tính bằng satoshi (1 BTC = 100,000,000 satoshi)
- Sử dụng DecimalField để tránh floating point errors
- Chỉ tính UTXO (outputs chưa spend)

## Error Handling

### 1. **Địa chỉ không tồn tại trong database**

```python
# Return 0 balance
if not address_obj:
    return 0
```

### 2. **Lỗi database**

```python
try:
    # Tính toán
except Exception as e:
    print(f"Lỗi: {e}")
    return 0
```

## Mở Rộng Tương Lai

1. **Real-time Updates**: Webhook để cập nhật khi có transaction mới
2. **Background Jobs**: Celery tasks để cập nhật định kỳ
3. **Multiple Currencies**: Hỗ trợ tính số dư theo USD, VND
4. **Transaction History**: Lưu lịch sử thay đổi số dư
