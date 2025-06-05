from django.core.management.base import BaseCommand
from bitcoin.models import Transaction, TxInput, Address, AddressCluster
from django.db.models import Q
from django.db import transaction as db_transaction
from django.utils import timezone
import logging
import uuid

logger = logging.getLogger(__name__)

class UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def make_set(self, element):
        """Khởi tạo một tập hợp cho phần tử."""
        if element not in self.parent:
            self.parent[element] = element
            self.rank[element] = 0

    def find(self, element):
        """Tìm đại diện (root) của cụm chứa phần tử, sử dụng path compression."""
        if element not in self.parent:
            self.make_set(element)
        if self.parent[element] != element:
            self.parent[element] = self.find(self.parent[element])
        return self.parent[element]

    def union(self, element1, element2):
        """Hợp nhất hai cụm, sử dụng union by rank."""
        root1 = self.find(element1)
        root2 = self.find(element2)
        if root1 != root2:
            if self.rank[root1] < self.rank[root2]:
                root1, root2 = root2, root1
            self.parent[root2] = root1
            if self.rank[root1] == self.rank[root2]:
                self.rank[root1] += 1

def add_tag(obj, tag_to_add):
    """Hàm trợ giúp để thêm tag mà không trùng lặp và trả về True nếu có thay đổi."""
    current_tags = set(obj.tags.split(',') if obj.tags else [])
    if tag_to_add not in current_tags:
        current_tags.add(tag_to_add)
        obj.tags = ','.join(filter(None, current_tags))
        return True
    return False

class Command(BaseCommand):
    help = 'Clusters addresses based on common input ownership using Union-Find.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full-rescan',
            action='store_true',
            help='Rescan all transactions and addresses for clustering.',
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=1000,
            help='Number of transactions to process in each chunk.',
        )
        parser.add_argument(
            '--start-block',
            type=int,
            help='Start analysis from this block height.',
        )

    def cluster_addresses(self, transactions_chunk):
        """Thực hiện phân cụm địa chỉ bằng Union-Find."""
        uf = UnionFind()
        # Khởi tạo tất cả địa chỉ trong lô giao dịch
        for tx in transactions_chunk:
            input_addresses = {inp.address.address for inp in tx.inputs.all() if inp.address}
            for addr in input_addresses:
                uf.make_set(addr)

        # Hợp nhất các địa chỉ đầu vào trong cùng giao dịch
        for tx in transactions_chunk:
            input_addresses = [inp.address.address for inp in tx.inputs.all() if inp.address]
            if len(input_addresses) > 1:  # Chỉ xử lý giao dịch có nhiều địa chỉ đầu vào
                first_addr = input_addresses[0]
                for addr in input_addresses[1:]:
                    uf.union(first_addr, addr)

        # Tạo danh sách cụm
        clusters = {}
        for addr in uf.parent:
            root = uf.find(addr)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(addr)

        return clusters

    def save_clusters(self, clusters):
        """Lưu các cụm vào bảng AddressCluster và cập nhật Address."""
        cluster_update_list = []
        address_update_list = []

        for root, addresses in clusters.items():
            if len(addresses) < 2:  # Bỏ qua cụm chỉ có 1 địa chỉ
                continue
            # Tạo hoặc lấy AddressCluster
            cluster_id = str(uuid.uuid4())
            cluster, created = AddressCluster.objects.get_or_create(
                cluster_id=cluster_id,
                defaults={'address_count': len(addresses)}
            )
            if not created:
                cluster.address_count = len(addresses)
                cluster_update_list.append(cluster)

            # Cập nhật Address
            for addr_str in addresses:
                try:
                    addr = Address.objects.get(address=addr_str)
                    addr.cluster = cluster
                    changed = add_tag(addr, 'clustered')
                    if changed or addr.cluster_id != cluster.cluster_id:
                        address_update_list.append(addr)
                except Address.DoesNotExist:
                    logger.warning(f"Address {addr_str} not found in database.")

        # Cập nhật cơ sở dữ liệu
        if cluster_update_list:
            AddressCluster.objects.bulk_update(
                cluster_update_list,
                ['address_count', 'updated_at'],
                batch_size=500
            )
        if address_update_list:
            Address.objects.bulk_update(
                address_update_list,
                ['cluster', 'tags'],
                batch_size=1000
            )
        return len(cluster_update_list), len(address_update_list)

    @db_transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Starting address clustering...")

        full_rescan = kwargs['full_rescan']
        chunk_size = kwargs['chunk_size']
        start_block = kwargs.get('start_block')

        # Lọc giao dịch
        if full_rescan:
            self.stdout.write("Performing a full rescan for clustering...")
            transaction_queryset = Transaction.objects.all()
        else:
            self.stdout.write("Clustering based on untagged or unclustered items...")
            # Chỉ xử lý các giao dịch có khả năng ảnh hưởng đến cụm mới
            transaction_queryset = Transaction.objects.filter(
                Q(inputs__address__cluster__isnull=True) |
                Q(tags__contains='multi_input_addr')
            ).distinct()

        if start_block:
            transaction_queryset = transaction_queryset.filter(block__height__gte=start_block)

        tx_count = transaction_queryset.count()
        self.stdout.write(f"Found {tx_count} transactions to analyze for clustering.")

        # Xử lý theo lô
        for i in range(0, tx_count, chunk_size):
            tx_chunk = list(transaction_queryset[i:i + chunk_size].prefetch_related('inputs', 'inputs__address'))
            self.stdout.write(f"Processing chunk {i//chunk_size + 1}...")

            # Phân cụm địa chỉ
            clusters = self.cluster_addresses(tx_chunk)
            num_clusters, num_addresses = self.save_clusters(clusters)
            self.stdout.write(f"Created/Updated {num_clusters} clusters and {num_addresses} addresses.")

        self.stdout.write(self.style.SUCCESS("Address clustering complete."))