from django.core.management.base import BaseCommand
from bitcoin.models import Transaction, TxOutput, Address, TxInput
from django.db.models import Sum, Count, Q, F
from django.db import transaction as db_transaction
from django.utils import timezone
import logging
from decimal import Decimal
import statistics
import json
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional

logger = logging.getLogger(__name__)

class AddressTree:
    """Cấu trúc cây địa chỉ để theo dõi quan hệ sở hữu"""
    
    def __init__(self):
        self.nodes = {}  # address -> node_info
        self.edges = defaultdict(set)  # address -> set of connected addresses
        self.clusters = defaultdict(set)  # cluster_id -> set of addresses
        self.cluster_counter = 0
    
    def add_address(self, address: str, cluster_id: Optional[str] = None):
        """Thêm địa chỉ vào cây"""
        if address not in self.nodes:
            self.nodes[address] = {
                'cluster_id': cluster_id or f"cluster_{self.cluster_counter}",
                'first_seen': timezone.now(),
                'tx_count': 0,
                'total_value': 0,
                'tags': set()
            }
            if cluster_id is None:
                self.cluster_counter += 1
    
    def connect_addresses(self, address1: str, address2: str):
        """Kết nối hai địa chỉ (cùng sở hữu)"""
        self.add_address(address1)
        self.add_address(address2)
        
        # Thêm edge
        self.edges[address1].add(address2)
        self.edges[address2].add(address1)
        
        # Hợp nhất clusters nếu cần
        self._merge_clusters(address1, address2)
    
    def _merge_clusters(self, addr1: str, addr2: str):
        """Hợp nhất clusters của hai địa chỉ"""
        cluster1 = self.nodes[addr1]['cluster_id']
        cluster2 = self.nodes[addr2]['cluster_id']
        
        if cluster1 != cluster2:
            # Chuyển tất cả địa chỉ từ cluster2 sang cluster1
            for addr, info in self.nodes.items():
                if info['cluster_id'] == cluster2:
                    info['cluster_id'] = cluster1
                    self.clusters[cluster1].add(addr)
            # Xóa cluster2
            if cluster2 in self.clusters:
                del self.clusters[cluster2]
    
    def get_cluster(self, address: str) -> Set[str]:
        """Lấy tất cả địa chỉ trong cùng cluster"""
        if address not in self.nodes:
            return {address}
        cluster_id = self.nodes[address]['cluster_id']
        return self.clusters.get(cluster_id, {address})
    
    def get_address_path(self, start_addr: str, end_addr: str, max_depth: int = 5) -> List[str]:
        """Tìm đường đi giữa hai địa chỉ (BFS)"""
        if start_addr == end_addr:
            return [start_addr]
        
        visited = set()
        queue = deque([(start_addr, [start_addr])])
        
        while queue and len(queue[0][1]) <= max_depth:
            current, path = queue.popleft()
            
            for neighbor in self.edges[current]:
                if neighbor == end_addr:
                    return path + [neighbor]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return []

class AdvancedCoinJoinDetector:
    """Phát hiện CoinJoin với đệ quy và ma trận cây địa chỉ"""
    
    def __init__(self):
        self.address_tree = AddressTree()
        self.transaction_graph = defaultdict(dict)  # Thay thế nx.DiGraph
        self.coinjoin_patterns = []
        
    def build_address_tree(self, transactions: List[Transaction], max_depth: int = 3):
        """Xây dựng cây địa chỉ từ lịch sử giao dịch"""
        logger.info(f"Building address tree from {len(transactions)} transactions...")
        
        for tx in transactions:
            # Thêm tất cả địa chỉ vào cây
            input_addresses = {inp.address.address for inp in tx.inputs.all() if inp.address}
            output_addresses = {out.address.address for out in tx.outputs.all() if out.address}
            
            for addr in input_addresses | output_addresses:
                self.address_tree.add_address(addr)
            
            # Kết nối các địa chỉ input (cùng sở hữu)
            if len(input_addresses) > 1:
                addr_list = list(input_addresses)
                for i in range(len(addr_list) - 1):
                    self.address_tree.connect_addresses(addr_list[i], addr_list[i + 1])
            
            # Thêm vào transaction graph
            self.transaction_graph[tx.hash] = {
                'time': tx.time,
                'fee': tx.fee,
                'input_count': len(input_addresses),
                'output_count': len(output_addresses)
            }

            # Thêm edges từ input addresses đến transaction
            for addr in input_addresses:
                if 'edges' not in self.transaction_graph[tx.hash]:
                    self.transaction_graph[tx.hash]['edges'] = {}
                self.transaction_graph[tx.hash]['edges'][addr] = {'type': 'input'}

            # Thêm edges từ transaction đến output addresses
            for out in tx.outputs.all():
                if out.address:
                    if 'edges' not in self.transaction_graph[tx.hash]:
                        self.transaction_graph[tx.hash]['edges'] = {}
                    self.transaction_graph[tx.hash]['edges'][out.address.address] = {
                        'type': 'output', 
                        'value': out.value
                    }
    
    def detect_coinjoin_recursive(self, transaction: Transaction, depth: int = 0, max_depth: int = 3) -> Dict:
        """Phát hiện CoinJoin với đệ quy theo dõi các địa chỉ liên quan"""
        
        if depth > max_depth:
            return {'is_coinjoin': False, 'confidence': 0.0, 'reason': 'Max depth reached'}
        
        # Phân tích giao dịch hiện tại
        basic_analysis = self._analyze_transaction_basic(transaction)
        
        if not basic_analysis['is_coinjoin']:
            return basic_analysis
        
        # Đệ quy phân tích các giao dịch liên quan
        related_transactions = self._get_related_transactions(transaction, depth)
        recursive_analysis = self._analyze_related_transactions(transaction, related_transactions, depth + 1)
        
        # Kết hợp kết quả
        combined_confidence = (basic_analysis['confidence'] * 0.6 + 
                             recursive_analysis['confidence'] * 0.4)
        
        return {
            'is_coinjoin': combined_confidence > 0.7,
            'confidence': combined_confidence,
            'basic_analysis': basic_analysis,
            'recursive_analysis': recursive_analysis,
            'related_transactions': len(related_transactions),
            'depth': depth
        }
    
    def _analyze_transaction_basic(self, transaction: Transaction) -> Dict:
        """Phân tích cơ bản một giao dịch"""
        inputs = list(transaction.inputs.all())
        outputs = list(transaction.outputs.all())
        
        vin_count = len(inputs)
        vout_count = len(outputs)
        
        # Điều kiện cơ bản cho CoinJoin
        if vin_count < 10 or vout_count < 10:
            return {'is_coinjoin': False, 'confidence': 0.0, 'reason': 'Insufficient I/O count'}
        
        # Phân tích giá trị đầu ra
        output_values = [o.value for o in outputs if o.value > 0]
        if not output_values:
            return {'is_coinjoin': False, 'confidence': 0.0, 'reason': 'No valid outputs'}
        
        mean_value = statistics.mean(output_values)
        variance = statistics.variance(output_values) if len(output_values) > 1 else 0
        
        # Tính độ đồng đều của giá trị đầu ra
        uniformity_score = 1.0 - (variance / (mean_value ** 2)) if mean_value > 0 else 0
        
        # Phân tích địa chỉ input
        input_addresses = {inp.address.address for inp in inputs if inp.address}
        input_clusters = set()
        for addr in input_addresses:
            cluster = self.address_tree.get_cluster(addr)
            input_clusters.add(frozenset(cluster))
        
        # Tính điểm dựa trên các tiêu chí
        score = 0.0
        
        # Điểm cho số lượng I/O cao
        if vin_count >= 50 and vout_count >= 50:
            score += 0.3
        elif vin_count >= 20 and vout_count >= 20:
            score += 0.2
        elif vin_count >= 10 and vout_count >= 10:
            score += 0.1
        
        # Điểm cho độ đồng đều giá trị
        if uniformity_score > 0.9:
            score += 0.4
        elif uniformity_score > 0.8:
            score += 0.3
        elif uniformity_score > 0.7:
            score += 0.2
        
        # Điểm cho đa dạng địa chỉ input
        if len(input_clusters) >= 5:
            score += 0.3
        elif len(input_clusters) >= 3:
            score += 0.2
        elif len(input_clusters) >= 2:
            score += 0.1
        
        return {
            'is_coinjoin': score > 0.5,
            'confidence': min(score, 1.0),
            'score': score,
            'uniformity_score': uniformity_score,
            'input_clusters': len(input_clusters),
            'vin_count': vin_count,
            'vout_count': vout_count
        }
    
    def _get_related_transactions(self, transaction: Transaction, depth: int) -> List[Transaction]:
        """Lấy các giao dịch liên quan theo đệ quy"""
        related_txs = []
        
        # Lấy các địa chỉ input/output của giao dịch hiện tại
        input_addresses = {inp.address.address for inp in transaction.inputs.all() if inp.address}
        output_addresses = {out.address.address for out in transaction.outputs.all() if out.address}
        
        # Tìm các giao dịch trước đó (inputs)
        for addr in input_addresses:
            # Lấy các giao dịch mà địa chỉ này là output
            input_txs = Transaction.objects.filter(
                outputs__address__address=addr,
                time__lt=transaction.time
            ).order_by('-time')[:5]  # Giới hạn 5 giao dịch gần nhất
            
            related_txs.extend(input_txs)
        
        # Tìm các giao dịch sau đó (outputs)
        for addr in output_addresses:
            # Lấy các giao dịch mà địa chỉ này là input
            output_txs = Transaction.objects.filter(
                inputs__address__address=addr,
                time__gt=transaction.time
            ).order_by('time')[:5]  # Giới hạn 5 giao dịch gần nhất
            
            related_txs.extend(output_txs)
        
        return list(set(related_txs))  # Loại bỏ trùng lặp
    
    def _analyze_related_transactions(self, main_tx: Transaction, related_txs: List[Transaction], depth: int) -> Dict:
        """Phân tích các giao dịch liên quan"""
        if not related_txs:
            return {'confidence': 0.0, 'pattern_matches': 0}
        
        pattern_matches = 0
        total_confidence = 0.0
        
        for tx in related_txs:
            analysis = self._analyze_transaction_basic(tx)
            if analysis['is_coinjoin']:
                pattern_matches += 1
                total_confidence += analysis['confidence']
        
        avg_confidence = total_confidence / len(related_txs) if related_txs else 0.0
        
        return {
            'confidence': avg_confidence,
            'pattern_matches': pattern_matches,
            'total_related': len(related_txs),
            'depth': depth
        }
    
    def create_address_matrix(self, transaction: Transaction) -> Dict:
        """Tạo ma trận cây địa chỉ cho một giao dịch"""
        input_addresses = {inp.address.address for inp in transaction.inputs.all() if inp.address}
        output_addresses = {out.address.address for out in transaction.outputs.all() if out.address}
        
        matrix = {
            'transaction_hash': transaction.hash,
            'time': transaction.time.isoformat(),
            'input_clusters': {},
            'output_clusters': {},
            'connections': [],
            'coinjoin_indicators': {}
        }
        
        # Phân tích clusters của input addresses
        for addr in input_addresses:
            cluster = self.address_tree.get_cluster(addr)
            cluster_id = f"input_cluster_{len(matrix['input_clusters'])}"
            matrix['input_clusters'][cluster_id] = {
                'addresses': list(cluster),
                'size': len(cluster),
                'total_value': sum(self._get_address_value(a) for a in cluster)
            }
        
        # Phân tích clusters của output addresses
        for addr in output_addresses:
            cluster = self.address_tree.get_cluster(addr)
            cluster_id = f"output_cluster_{len(matrix['output_clusters'])}"
            matrix['output_clusters'][cluster_id] = {
                'addresses': list(cluster),
                'size': len(cluster),
                'total_value': sum(self._get_address_value(a) for a in cluster)
            }
        
        # Tìm connections giữa các clusters
        for input_cluster_id, input_cluster in matrix['input_clusters'].items():
            for output_cluster_id, output_cluster in matrix['output_clusters'].items():
                # Kiểm tra xem có địa chỉ nào trong input cluster xuất hiện trong output cluster không
                common_addresses = set(input_cluster['addresses']) & set(output_cluster['addresses'])
                if common_addresses:
                    matrix['connections'].append({
                        'from': input_cluster_id,
                        'to': output_cluster_id,
                        'common_addresses': list(common_addresses),
                        'connection_strength': len(common_addresses)
                    })
        
        # Tính các chỉ số CoinJoin
        matrix['coinjoin_indicators'] = {
            'input_cluster_diversity': len(matrix['input_clusters']),
            'output_cluster_diversity': len(matrix['output_clusters']),
            'total_connections': len(matrix['connections']),
            'average_cluster_size': (len(input_addresses) + len(output_addresses)) / 
                                  (len(matrix['input_clusters']) + len(matrix['output_clusters'])) if (len(matrix['input_clusters']) + len(matrix['output_clusters'])) > 0 else 0
        }
        
        return matrix
    
    def _get_address_value(self, address: str) -> int:
        """Lấy tổng giá trị của một địa chỉ"""
        try:
            addr_obj = Address.objects.get(address=address)
            return TxOutput.objects.filter(
                address=addr_obj,
                is_spent=False
            ).aggregate(total=Sum('value'))['total'] or 0
        except Address.DoesNotExist:
            return 0

class Command(BaseCommand):
    help = 'Advanced CoinJoin detection with recursive analysis and address tree matrix'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--start-block',
            type=int,
            help='Start analysis from this block height.',
        )
        parser.add_argument(
            '--end-block',
            type=int,
            help='End analysis at this block height.',
        )
        parser.add_argument(
            '--max-depth',
            type=int,
            default=3,
            help='Maximum recursion depth for analysis.',
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file for detailed analysis results.',
        )
    
    def handle(self, *args, **kwargs):
        self.stdout.write("Starting advanced CoinJoin detection...")
        
        detector = AdvancedCoinJoinDetector()
        
        # Lấy giao dịch để phân tích
        queryset = Transaction.objects.all()
        
        if kwargs.get('start_block'):
            queryset = queryset.filter(block__height__gte=kwargs['start_block'])
        
        if kwargs.get('end_block'):
            queryset = queryset.filter(block__height__lte=kwargs['end_block'])
        
        # Giới hạn số lượng giao dịch để test
        transactions = list(queryset.order_by('-time')[:1000])
        
        self.stdout.write(f"Building address tree from {len(transactions)} transactions...")
        detector.build_address_tree(transactions, kwargs.get('max_depth', 3))
        
        # Phát hiện CoinJoin
        coinjoin_results = []
        for tx in transactions:
            if tx.inputs.count() >= 10 and tx.outputs.count() >= 10:  # Chỉ phân tích giao dịch có nhiều I/O
                result = detector.detect_coinjoin_recursive(tx, max_depth=kwargs.get('max_depth', 3))
                if result['is_coinjoin']:
                    matrix = detector.create_address_matrix(tx)
                    coinjoin_results.append({
                        'transaction': tx.hash,
                        'analysis': result,
                        'matrix': matrix
                    })
        
        self.stdout.write(f"Found {len(coinjoin_results)} potential CoinJoin transactions")
        
        # Lưu kết quả
        if kwargs.get('output_file'):
            with open(kwargs['output_file'], 'w') as f:
                json.dump(coinjoin_results, f, indent=2, default=str)
            self.stdout.write(f"Results saved to {kwargs['output_file']}")
        
        # In kết quả tóm tắt
        for result in coinjoin_results[:10]:  # Chỉ in 10 kết quả đầu
            tx_hash = result['transaction']
            confidence = result['analysis']['confidence']
            self.stdout.write(f"CoinJoin detected: {tx_hash[:16]}... (confidence: {confidence:.2f})")
        
        self.stdout.write(self.style.SUCCESS("Advanced CoinJoin detection complete.")) 