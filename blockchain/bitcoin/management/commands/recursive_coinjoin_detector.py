from django.core.management.base import BaseCommand
from bitcoin.models import Transaction, Address, TxInput, TxOutput
from django.db.models import Q
from collections import defaultdict, deque
import networkx as nx
import json
import logging
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RecursiveCoinJoinDetector:
    """Phát hiện CoinJoin theo dạng đệ quy với đồ thị"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.coinjoin_clusters = []
        self.address_clusters = defaultdict(set)
        self.transaction_paths = defaultdict(list)
        
    def build_transaction_graph(self, max_depth=5, max_transactions=1000):
        """Xây dựng đồ thị giao dịch từ database"""
        logger.info("Building transaction graph...")
        
        # Lấy tất cả giao dịch có nhiều input/output (candidate CoinJoin)
        candidate_txs = Transaction.objects.filter(
            vin_sz__gte=5,  # Ít nhất 5 inputs
            vout_sz__gte=5   # Ít nhất 5 outputs
        ).order_by('-time')[:max_transactions]
        
        logger.info(f"Found {len(candidate_txs)} candidate transactions")
        
        # Xây dựng đồ thị
        for tx in candidate_txs:
            self._add_transaction_to_graph(tx)
            
        # Tìm các đường đi đệ quy
        self._find_recursive_paths(max_depth)
        
        return self.graph
    
    def _add_transaction_to_graph(self, tx: Transaction):
        """Thêm giao dịch vào đồ thị"""
        # Thêm node giao dịch
        self.graph.add_node(tx.hash, 
                           type='transaction',
                           time=tx.time,
                           fee=tx.fee,
                           input_count=tx.vin_sz,
                           output_count=tx.vout_sz,
                           tags=tx.tags)
        
        # Lấy tất cả địa chỉ input
        input_addresses = set()
        for inp in tx.inputs.all():
            if inp.address:
                addr = inp.address.address
                input_addresses.add(addr)
                
                # Thêm node địa chỉ nếu chưa có
                if not self.graph.has_node(addr):
                    self.graph.add_node(addr, 
                                      type='address',
                                      first_seen=inp.address.first_seen,
                                      tags=inp.address.tags)
                
                # Thêm edge từ địa chỉ đến giao dịch
                self.graph.add_edge(addr, tx.hash, 
                                  type='input',
                                  value=inp.prev_value or 0)
        
        # Lấy tất cả địa chỉ output
        output_addresses = set()
        for out in tx.outputs.all():
            if out.address:
                addr = out.address.address
                output_addresses.add(addr)
                
                # Thêm node địa chỉ nếu chưa có
                if not self.graph.has_node(addr):
                    self.graph.add_node(addr, 
                                      type='address',
                                      first_seen=out.address.first_seen,
                                      tags=out.address.tags)
                
                # Thêm edge từ giao dịch đến địa chỉ
                self.graph.add_edge(tx.hash, addr, 
                                  type='output',
                                  value=out.value)
        
        # Kiểm tra xem có phải CoinJoin không
        if self._is_coinjoin_transaction(tx, input_addresses, output_addresses):
            self.graph.nodes[tx.hash]['is_coinjoin'] = True
            self._mark_coinjoin_addresses(input_addresses, output_addresses)
    
    def _is_coinjoin_transaction(self, tx: Transaction, input_addrs: Set[str], output_addrs: Set[str]) -> bool:
        """Kiểm tra xem giao dịch có phải CoinJoin không"""
        # Tiêu chí cơ bản
        if len(input_addrs) < 5 or len(output_addrs) < 5:
            return False
        
        # Kiểm tra độ đồng đều của output values
        output_values = [out.value for out in tx.outputs.all()]
        if len(output_values) < 5:
            return False
        
        mean_value = sum(output_values) / len(output_values)
        variance = sum((v - mean_value) ** 2 for v in output_values) / len(output_values)
        coefficient_of_variation = (variance ** 0.5) / mean_value
        
        # Nếu độ biến thiên < 5%, có thể là CoinJoin
        if coefficient_of_variation < 0.05:
            return True
        
        # Kiểm tra thêm các tiêu chí khác
        if tx.vin_sz >= 10 and tx.vout_sz >= 10:
            return True
            
        return False
    
    def _mark_coinjoin_addresses(self, input_addrs: Set[str], output_addrs: Set[str]):
        """Đánh dấu các địa chỉ liên quan đến CoinJoin"""
        for addr in input_addrs | output_addrs:
            if self.graph.has_node(addr):
                current_tags = self.graph.nodes[addr].get('tags', '') or ''
                if 'coinjoin' not in current_tags:
                    new_tags = f"{current_tags},coinjoin" if current_tags else "coinjoin"
                    self.graph.nodes[addr]['tags'] = new_tags
    
    def _find_recursive_paths(self, max_depth: int):
        """Tìm các đường đi đệ quy trong đồ thị"""
        logger.info("Finding recursive paths...")
        
        # Tìm tất cả địa chỉ CoinJoin
        coinjoin_addresses = [node for node, data in self.graph.nodes(data=True) 
                            if data.get('type') == 'address' and 'coinjoin' in (data.get('tags', '') or '')]
        
        for start_addr in coinjoin_addresses:
            self._explore_recursive_paths(start_addr, max_depth)
    
    def _explore_recursive_paths(self, start_addr: str, max_depth: int):
        """Khám phá đường đi đệ quy từ một địa chỉ"""
        visited = set()
        paths = []
        
        def dfs(current_addr: str, path: List[str], depth: int):
            if depth > max_depth or current_addr in visited:
                return
            
            visited.add(current_addr)
            path.append(current_addr)
            
            # Tìm tất cả giao dịch liên quan
            for neighbor in self.graph.neighbors(current_addr):
                if self.graph.nodes[neighbor].get('type') == 'transaction':
                    path.append(neighbor)
                    
                    # Tìm các địa chỉ output
                    for output_addr in self.graph.successors(neighbor):
                        if self.graph.nodes[output_addr].get('type') == 'address':
                            dfs(output_addr, path.copy(), depth + 1)
            
            # Nếu đường đi có ít nhất 2 giao dịch và quay lại địa chỉ ban đầu
            if len(path) >= 3 and path[-1] == start_addr:
                paths.append(path)
        
        dfs(start_addr, [], 0)
        
        # Lưu các đường đi đệ quy
        if paths:
            self.transaction_paths[start_addr] = paths
    
    def detect_coinjoin_clusters(self):
        """Phát hiện các cluster CoinJoin"""
        logger.info("Detecting CoinJoin clusters...")
        
        # Tìm các thành phần liên thông trong đồ thị
        components = list(nx.strongly_connected_components(self.graph))
        
        for component in components:
            if len(component) >= 3:  # Ít nhất 3 node
                # Kiểm tra xem component có chứa CoinJoin không
                has_coinjoin = False
                addresses = set()
                transactions = set()
                
                for node in component:
                    node_data = self.graph.nodes[node]
                    if node_data.get('type') == 'transaction' and node_data.get('is_coinjoin'):
                        has_coinjoin = True
                    elif node_data.get('type') == 'address':
                        addresses.add(node)
                    elif node_data.get('type') == 'transaction':
                        transactions.add(node)
                
                if has_coinjoin:
                    cluster = {
                        'id': f"cluster_{len(self.coinjoin_clusters)}",
                        'addresses': list(addresses),
                        'transactions': list(transactions),
                        'size': len(component),
                        'coinjoin_count': len([t for t in transactions 
                                             if self.graph.nodes[t].get('is_coinjoin')])
                    }
                    self.coinjoin_clusters.append(cluster)
                    
                    # Cập nhật address clusters
                    for addr in addresses:
                        self.address_clusters[addr].add(cluster['id'])
    
    def get_recursive_analysis(self, target_address: str, max_depth: int = 3) -> Dict:
        """Phân tích đệ quy cho một địa chỉ cụ thể"""
        if not self.graph.has_node(target_address):
            return {'error': 'Address not found in graph'}
        
        analysis = {
            'address': target_address,
            'depth': max_depth,
            'paths': [],
            'related_addresses': set(),
            'related_transactions': set(),
            'coinjoin_transactions': set()
        }
        
        # Tìm tất cả đường đi từ địa chỉ này
        visited = set()
        
        def explore_paths(current_addr: str, path: List[str], depth: int):
            if depth > max_depth or current_addr in visited:
                return
            
            visited.add(current_addr)
            path.append(current_addr)
            analysis['related_addresses'].add(current_addr)
            
            # Tìm các giao dịch liên quan
            for neighbor in self.graph.neighbors(current_addr):
                if self.graph.nodes[neighbor].get('type') == 'transaction':
                    path.append(neighbor)
                    analysis['related_transactions'].add(neighbor)
                    
                    if self.graph.nodes[neighbor].get('is_coinjoin'):
                        analysis['coinjoin_transactions'].add(neighbor)
                    
                    # Tìm các địa chỉ output
                    for output_addr in self.graph.successors(neighbor):
                        if self.graph.nodes[output_addr].get('type') == 'address':
                            explore_paths(output_addr, path.copy(), depth + 1)
        
        explore_paths(target_address, [], 0)
        
        # Chuyển sets thành lists cho JSON serialization
        analysis['related_addresses'] = list(analysis['related_addresses'])
        analysis['related_transactions'] = list(analysis['related_transactions'])
        analysis['coinjoin_transactions'] = list(analysis['coinjoin_transactions'])
        
        return analysis
    
    def export_graph_data(self) -> Dict:
        """Xuất dữ liệu đồ thị cho visualization"""
        nodes = []
        edges = []
        
        for node, data in self.graph.nodes(data=True):
            node_data = {
                'id': node,
                'type': data.get('type', 'unknown'),
                'tags': data.get('tags', '') or '',
                'is_coinjoin': data.get('is_coinjoin', False)
            }
            
            if data.get('type') == 'transaction':
                node_data.update({
                    'time': data.get('time').isoformat() if data.get('time') else None,
                    'fee': data.get('fee', 0),
                    'input_count': data.get('input_count', 0),
                    'output_count': data.get('output_count', 0)
                })
            
            nodes.append(node_data)
        
        for source, target, data in self.graph.edges(data=True):
            edge_data = {
                'source': source,
                'target': target,
                'type': data.get('type', 'unknown'),
                'value': data.get('value', 0)
            }
            edges.append(edge_data)
        
        return {
            'nodes': nodes,
            'edges': edges,
            'clusters': self.coinjoin_clusters
        }

class Command(BaseCommand):
    help = 'Phát hiện CoinJoin theo dạng đệ quy với đồ thị'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--build-graph',
            action='store_true',
            help='Xây dựng đồ thị giao dịch',
        )
        parser.add_argument(
            '--analyze-address',
            type=str,
            help='Phân tích đệ quy cho một địa chỉ cụ thể',
        )
        parser.add_argument(
            '--export-graph',
            action='store_true',
            help='Xuất dữ liệu đồ thị',
        )
        parser.add_argument(
            '--max-depth',
            type=int,
            default=5,
            help='Độ sâu tối đa cho đệ quy',
        )
        parser.add_argument(
            '--max-transactions',
            type=int,
            default=1000,
            help='Số lượng giao dịch tối đa để phân tích',
        )
    
    def handle(self, *args, **kwargs):
        detector = RecursiveCoinJoinDetector()
        
        if kwargs.get('build_graph'):
            self.build_graph(detector, kwargs)
        elif kwargs.get('analyze_address'):
            self.analyze_address(detector, kwargs['analyze_address'], kwargs)
        elif kwargs.get('export_graph'):
            self.export_graph(detector, kwargs)
        else:
            self.stdout.write("Use --build-graph to build graph, --analyze-address ADDRESS to analyze specific address, or --export-graph to export graph data")
    
    def build_graph(self, detector: RecursiveCoinJoinDetector, kwargs: Dict):
        """Xây dựng đồ thị giao dịch"""
        self.stdout.write("Building transaction graph...")
        
        max_depth = kwargs.get('max_depth', 5)
        max_transactions = kwargs.get('max_transactions', 1000)
        
        graph = detector.build_transaction_graph(max_depth, max_transactions)
        
        self.stdout.write(f"Graph built with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
        
        # Phát hiện clusters
        detector.detect_coinjoin_clusters()
        
        self.stdout.write(f"Found {len(detector.coinjoin_clusters)} CoinJoin clusters")
        
        # Hiển thị thống kê
        coinjoin_txs = [node for node, data in graph.nodes(data=True) 
                       if data.get('is_coinjoin')]
        coinjoin_addrs = [node for node, data in graph.nodes(data=True) 
                         if data.get('type') == 'address' and 'coinjoin' in (data.get('tags', '') or '')]
        
        self.stdout.write(f"CoinJoin transactions: {len(coinjoin_txs)}")
        self.stdout.write(f"CoinJoin addresses: {len(coinjoin_addrs)}")
        
        self.stdout.write(self.style.SUCCESS("Graph building complete!"))
    
    def analyze_address(self, detector: RecursiveCoinJoinDetector, address: str, kwargs: Dict):
        """Phân tích đệ quy cho một địa chỉ"""
        self.stdout.write(f"Analyzing address: {address}")
        
        # Xây dựng đồ thị trước
        max_depth = kwargs.get('max_depth', 5)
        max_transactions = kwargs.get('max_transactions', 1000)
        
        detector.build_transaction_graph(max_depth, max_transactions)
        detector.detect_coinjoin_clusters()
        
        # Phân tích địa chỉ
        analysis = detector.get_recursive_analysis(address, max_depth)
        
        if 'error' in analysis:
            self.stdout.write(self.style.ERROR(analysis['error']))
            return
        
        self.stdout.write(f"Analysis for {address}:")
        self.stdout.write(f"  Related addresses: {len(analysis['related_addresses'])}")
        self.stdout.write(f"  Related transactions: {len(analysis['related_transactions'])}")
        self.stdout.write(f"  CoinJoin transactions: {len(analysis['coinjoin_transactions'])}")
        
        # Hiển thị các giao dịch CoinJoin
        if analysis['coinjoin_transactions']:
            self.stdout.write("\nCoinJoin transactions:")
            for tx_hash in analysis['coinjoin_transactions'][:5]:  # Hiển thị 5 giao dịch đầu
                tx_data = detector.graph.nodes[tx_hash]
                self.stdout.write(f"  {tx_hash[:16]}... - {tx_data.get('input_count', 0)} inputs, {tx_data.get('output_count', 0)} outputs")
        
        self.stdout.write(self.style.SUCCESS("Analysis complete!"))
    
    def export_graph(self, detector: RecursiveCoinJoinDetector, kwargs: Dict):
        """Xuất dữ liệu đồ thị"""
        self.stdout.write("Exporting graph data...")
        
        # Xây dựng đồ thị trước
        max_depth = kwargs.get('max_depth', 5)
        max_transactions = kwargs.get('max_transactions', 1000)
        
        detector.build_transaction_graph(max_depth, max_transactions)
        detector.detect_coinjoin_clusters()
        
        # Xuất dữ liệu
        graph_data = detector.export_graph_data()
        
        # Lưu vào file
        with open('coinjoin_graph_data.json', 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, default=str)
        
        self.stdout.write(f"Graph data exported to coinjoin_graph_data.json")
        self.stdout.write(f"  Nodes: {len(graph_data['nodes'])}")
        self.stdout.write(f"  Edges: {len(graph_data['edges'])}")
        self.stdout.write(f"  Clusters: {len(graph_data['clusters'])}")
        
        self.stdout.write(self.style.SUCCESS("Export complete!")) 