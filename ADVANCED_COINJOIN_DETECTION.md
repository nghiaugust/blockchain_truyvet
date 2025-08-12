# Advanced CoinJoin Detection với Đệ Quy và Ma Trận Cây Địa Chỉ

## Tổng Quan

Hệ thống phát hiện CoinJoin cải tiến sử dụng đệ quy để theo dõi các địa chỉ liên quan và tạo ma trận cây địa chỉ để phân tích mối quan hệ sở hữu.

## Các Thành Phần Chính

### 1. **AddressTree** (`advanced_coinjoin.py`)
Cấu trúc cây địa chỉ để theo dõi quan hệ sở hữu:

```python
class AddressTree:
    def __init__(self):
        self.nodes = {}  # address -> node_info
        self.edges = defaultdict(set)  # address -> set of connected addresses
        self.clusters = defaultdict(set)  # cluster_id -> set of addresses
```

**Chức năng chính:**
- `add_address()`: Thêm địa chỉ vào cây
- `connect_addresses()`: Kết nối hai địa chỉ (cùng sở hữu)
- `get_cluster()`: Lấy tất cả địa chỉ trong cùng cluster
- `get_address_path()`: Tìm đường đi giữa hai địa chỉ (BFS)

### 2. **AdvancedCoinJoinDetector** (`advanced_coinjoin.py`)
Phát hiện CoinJoin với đệ quy và ma trận cây địa chỉ:

```python
class AdvancedCoinJoinDetector:
    def __init__(self):
        self.address_tree = AddressTree()
        self.transaction_graph = nx.DiGraph()
        self.coinjoin_patterns = []
```

**Chức năng chính:**
- `build_address_tree()`: Xây dựng cây địa chỉ từ lịch sử giao dịch
- `detect_coinjoin_recursive()`: Phát hiện CoinJoin với đệ quy
- `create_address_matrix()`: Tạo ma trận cây địa chỉ

## Thuật Toán Phát Hiện CoinJoin

### 1. **Phân Tích Cơ Bản**
```python
def _analyze_transaction_basic(self, transaction: Transaction) -> Dict:
    # Điều kiện: ≥ 10 inputs và ≥ 10 outputs
    if vin_count < 10 or vout_count < 10:
        return {'is_coinjoin': False, 'confidence': 0.0}
    
    # Phân tích độ đồng đều giá trị đầu ra
    uniformity_score = 1.0 - (variance / (mean_value ** 2))
    
    # Phân tích đa dạng địa chỉ input
    input_clusters = set()
    for addr in input_addresses:
        cluster = self.address_tree.get_cluster(addr)
        input_clusters.add(frozenset(cluster))
```

### 2. **Phân Tích Đệ Quy**
```python
def detect_coinjoin_recursive(self, transaction: Transaction, depth: int = 0, max_depth: int = 3) -> Dict:
    # Phân tích giao dịch hiện tại
    basic_analysis = self._analyze_transaction_basic(transaction)
    
    # Đệ quy phân tích các giao dịch liên quan
    related_transactions = self._get_related_transactions(transaction, depth)
    recursive_analysis = self._analyze_related_transactions(transaction, related_transactions, depth + 1)
    
    # Kết hợp kết quả
    combined_confidence = (basic_analysis['confidence'] * 0.6 + 
                         recursive_analysis['confidence'] * 0.4)
```

### 3. **Ma Trận Cây Địa Chỉ**
```python
def create_address_matrix(self, transaction: Transaction) -> Dict:
    matrix = {
        'transaction_hash': transaction.hash,
        'input_clusters': {},
        'output_clusters': {},
        'connections': [],
        'coinjoin_indicators': {}
    }
    
    # Phân tích clusters của input addresses
    for addr in input_addresses:
        cluster = self.address_tree.get_cluster(addr)
        matrix['input_clusters'][cluster_id] = {
            'addresses': list(cluster),
            'size': len(cluster),
            'total_value': sum(self._get_address_value(a) for a in cluster)
        }
```

## Cách Sử Dụng

### 1. **Chạy Demo**
```bash
# Phân tích một giao dịch cụ thể
python manage.py demo_coinjoin --tx-hash <transaction_hash> --max-depth 3

# Phân tích nhiều giao dịch
python manage.py demo_coinjoin --limit 20 --max-depth 3
```

### 2. **Chạy Enhanced Heuristics**
```bash
# Phân tích với CoinJoin detection nâng cao
python manage.py enhanced_heuristics --enable-advanced-coinjoin --max-depth 3

# Phân tích từ block cụ thể
python manage.py enhanced_heuristics --start-block 800000 --enable-advanced-coinjoin
```

### 3. **Chạy Advanced CoinJoin Detection**
```bash
# Phát hiện CoinJoin với output chi tiết
python manage.py advanced_coinjoin --start-block 800000 --output-file results.json
```

## Output Mẫu

### 1. **Kết Quả Phân Tích CoinJoin**
```json
{
  "transaction": "abc123...",
  "analysis": {
    "is_coinjoin": true,
    "confidence": 0.85,
    "basic_analysis": {
      "uniformity_score": 0.92,
      "input_clusters": 5,
      "vin_count": 25,
      "vout_count": 25
    },
    "recursive_analysis": {
      "pattern_matches": 3,
      "total_related": 8,
      "depth": 2
    }
  },
  "matrix": {
    "input_clusters": {
      "input_cluster_0": {
        "addresses": ["addr1", "addr2", "addr3"],
        "size": 3,
        "total_value": 1000000000
      }
    },
    "coinjoin_indicators": {
      "input_cluster_diversity": 5,
      "output_cluster_diversity": 8,
      "total_connections": 12,
      "average_cluster_size": 4.2
    }
  }
}
```

### 2. **Ma Trận Cây Địa Chỉ**
```json
{
  "transaction_hash": "abc123...",
  "time": "2024-01-01T12:00:00Z",
  "input_clusters": {
    "input_cluster_0": {
      "addresses": ["1A1zP1...", "1B1zP1...", "1C1zP1..."],
      "size": 3,
      "total_value": 1500000000
    }
  },
  "output_clusters": {
    "output_cluster_0": {
      "addresses": ["1D1zP1...", "1E1zP1..."],
      "size": 2,
      "total_value": 750000000
    }
  },
  "connections": [
    {
      "from": "input_cluster_0",
      "to": "output_cluster_0",
      "common_addresses": ["1A1zP1..."],
      "connection_strength": 1
    }
  ]
}
```

## Ưu Điểm của Hệ Thống Cải Tiến

### 1. **Đệ Quy Phân Tích**
- Theo dõi các giao dịch liên quan theo thời gian
- Phát hiện pattern CoinJoin trong chuỗi giao dịch
- Tăng độ chính xác bằng cách phân tích context

### 2. **Ma Trận Cây Địa Chỉ**
- Mô hình hóa quan hệ sở hữu địa chỉ
- Phân tích đa dạng input/output clusters
- Theo dõi connections giữa các clusters

### 3. **Phân Tích Nâng Cao**
- Kết hợp nhiều tiêu chí (uniformity, diversity, patterns)
- Confidence scoring dựa trên nhiều yếu tố
- Caching và optimization cho hiệu suất

## So Sánh với Hệ Thống Cũ

| Tiêu Chí | Hệ Thống Cũ | Hệ Thống Cải Tiến |
|----------|-------------|-------------------|
| **Phân Tích** | Chỉ giao dịch hiện tại | Đệ quy theo dõi giao dịch liên quan |
| **Ma Trận** | Không có | Cây địa chỉ với clusters |
| **Confidence** | Đơn giản (0-1) | Kết hợp nhiều yếu tố |
| **Performance** | Nhanh | Chậm hơn nhưng chính xác hơn |
| **Accuracy** | Trung bình | Cao hơn |

## Cấu Hình và Tùy Chỉnh

### 1. **Ngưỡng Phát Hiện**
```python
# Trong advanced_coinjoin.py
HIGH_IO_THRESHOLD = 10  # Số lượng input/output tối thiểu
COINJOIN_VALUE_VARIANCE = Decimal('0.05')  # Độ đồng đều giá trị
```

### 2. **Độ Sâu Đệ Quy**
```python
# Tùy chỉnh max_depth
python manage.py demo_coinjoin --max-depth 5
```

### 3. **Confidence Threshold**
```python
# Trong detect_coinjoin_recursive()
combined_confidence > 0.7  # Ngưỡng confidence
```

## Troubleshooting

### 1. **Lỗi Memory**
- Giảm `max_depth` hoặc `chunk_size`
- Sử dụng `--limit` để giới hạn số giao dịch

### 2. **Performance Chậm**
- Tăng `chunk_size` để xử lý batch lớn hơn
- Sử dụng `--start-block` để phân tích từng phần

### 3. **Kết Quả Không Chính Xác**
- Điều chỉnh các ngưỡng trong code
- Kiểm tra dữ liệu input có đầy đủ không

## Tương Lai Phát Triển

1. **Machine Learning Integration**
   - Sử dụng ML để cải thiện accuracy
   - Auto-tuning các ngưỡng

2. **Real-time Detection**
   - Streaming analysis cho giao dịch mới
   - WebSocket updates

3. **Visualization**
   - Graph visualization cho address tree
   - Interactive matrix explorer

4. **API Integration**
   - REST API cho real-time queries
   - Webhook notifications 