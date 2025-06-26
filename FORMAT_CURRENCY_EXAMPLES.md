# Ví dụ cách filter format_currency hoạt động

## Input và Output Examples:

### Với VND:

- Input: total_balance_preferred = 1080000000.0, preferred_currency = "VND"
- Template: {{ 1080000000.0|format_currency:"VND" }}
- Output: "1,080,000,000 ₫"

### Với USD:

- Input: total_balance_preferred = 45000.50, preferred_currency = "USD"
- Template: {{ 45000.50|format_currency:"USD" }}
- Output: "$45,000.50"

### Với BTC:

- Input: total_balance_preferred = 1.50000000, preferred_currency = "BTC"
- Template: {{ 1.50000000|format_currency:"BTC" }}
- Output: "1.50000000 ₿"

## Format chi tiết:

### VND Format: `f"{value:,.0f} ₫"`

- `:,` = thêm dấu phẩy ngăn cách hàng nghìn
- `.0f` = 0 chữ số thập phân
- ` ₫` = thêm ký hiệu VND

### USD Format: `f"${value:,.2f}"`

- `$` = ký hiệu đô la ở đầu
- `:,` = dấu phẩy ngăn cách
- `.2f` = 2 chữ số thập phân

### BTC Format: `f"{value:.8f} ₿"`

- `.8f` = 8 chữ số thập phân (độ chính xác Bitcoin)
- ` ₿` = ký hiệu Bitcoin

## Ví dụ trong context thực tế:

Nếu user có 0.001 BTC và chọn VND:

1. total_balance = 0.001 (BTC)
2. exchange_rate = 1,080,000,000 VND/BTC
3. total_balance_preferred = 0.001 × 1,080,000,000 = 1,080,000
4. Template: {{ 1080000|format_currency:"VND" }}
5. Hiển thị: "1,080,000 ₫"
