from django.core.management.base import BaseCommand
from bitcoin.models import Transaction, Address, TxInput, TxOutput, Block
from django.db import transaction as db_transaction
from django.utils import timezone
import random
import hashlib
from decimal import Decimal

class Command(BaseCommand):
    help = 'Test CoinJoin Address Selector with sample data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample',
            action='store_true',
            help='Create sample CoinJoin transactions and addresses.',
        )
        parser.add_argument(
            '--check-data',
            action='store_true',
            help='Check existing CoinJoin data in database.',
        )
    
    def handle(self, *args, **kwargs):
        if kwargs.get('create_sample'):
            self.create_sample_data()
        elif kwargs.get('check_data'):
            self.check_existing_data()
        else:
            self.stdout.write("Use --create-sample to create sample data or --check-data to check existing data")
    
    def create_sample_data(self):
        """Tạo dữ liệu mẫu cho CoinJoin selector"""
        self.stdout.write("Creating sample CoinJoin data...")
        
        # Tạo block mẫu trước
        sample_block, created = Block.objects.get_or_create(
            hash="0000000000000000000000000000000000000000000000000000000000000000",
            defaults={
                'height': 999999,
                'time': timezone.now(),
                'n_tx': 10,
                'fee': 1000000
            }
        )
        
        # Tạo các địa chỉ mẫu
        addresses = []
        for i in range(50):
            addr = f"1SampleAddr{i:03d}ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            address_obj, created = Address.objects.get_or_create(
                address=addr,
                defaults={
                    'tx_count': random.randint(1, 20),
                    'tags': self.get_random_tags()
                }
            )
            addresses.append(address_obj)
        
        self.stdout.write(f"Created {len(addresses)} sample addresses")
        
        # Tạo các giao dịch CoinJoin mẫu
        coinjoin_transactions = []
        for i in range(10):
            # Tạo hash giao dịch mẫu
            tx_hash = hashlib.sha256(f"sample_coinjoin_tx_{i}".encode()).hexdigest()
            
            # Tạo giao dịch CoinJoin với nhiều input/output
            tx, created = Transaction.objects.get_or_create(
                hash=tx_hash,
                defaults={
                    'block': sample_block,
                    'tx_index': i,
                    'time': timezone.now() - timezone.timedelta(days=random.randint(1, 30)),
                    'fee': random.randint(1000, 50000),
                    'size': random.randint(500, 2000),
                    'weight': random.randint(1000, 4000),
                    'lock_time': 0,
                    'vin_sz': random.randint(5, 15),
                    'vout_sz': random.randint(5, 15),
                    'tags': 'coinjoin,high_io',
                    'anomaly_score': random.uniform(2.0, 8.0),
                    'total_output_value': random.randint(100000000, 1000000000),  # 1-10 BTC
                    'is_coinbase': False
                }
            )
            
            if created:
                # Tạo inputs (5-15 inputs)
                num_inputs = random.randint(5, 15)
                for j in range(num_inputs):
                    addr = random.choice(addresses)
                    TxInput.objects.create(
                        transaction=tx,
                        input_index=j,
                        address=addr,
                        prev_tx_hash=f"prev_tx_{i}_{j}",
                        prev_output_index=random.randint(0, 5),
                        prev_value=random.randint(1000000, 10000000),  # 0.01-0.1 BTC
                        sequence=0xFFFFFFFF
                    )
                
                # Tạo outputs (5-15 outputs với giá trị đồng đều)
                num_outputs = random.randint(5, 15)
                output_value = tx.total_output_value // num_outputs
                
                for j in range(num_outputs):
                    addr = random.choice(addresses)
                    TxOutput.objects.create(
                        transaction=tx,
                        output_index=j,
                        address=addr,
                        value=output_value,
                        script_pub_key=f"script_pub_key_{i}_{j}",
                        is_spent=False
                    )
                
                coinjoin_transactions.append(tx)
                self.stdout.write(f"Created CoinJoin transaction {i+1}: {tx_hash[:16]}...")
        
        self.stdout.write(f"Created {len(coinjoin_transactions)} sample CoinJoin transactions")
        
        # Cập nhật tags cho các địa chỉ liên quan
        for addr in addresses:
            if addr.tx_count > 5:
                addr.tags = (addr.tags or '') + ',clustered'
                addr.save()
        
        self.stdout.write(self.style.SUCCESS("Sample data creation complete!"))
    
    def get_random_tags(self):
        """Tạo tags ngẫu nhiên cho địa chỉ"""
        tags = []
        tag_options = ['coinjoin', 'clustered', 'high_reuse', 'reuse', 'new']
        
        # 30% khả năng có tag coinjoin
        if random.random() < 0.3:
            tags.append('coinjoin')
        
        # 40% khả năng có tag clustered
        if random.random() < 0.4:
            tags.append('clustered')
        
        # 20% khả năng có tag high_reuse
        if random.random() < 0.2:
            tags.append('high_reuse')
        
        # 30% khả năng có tag reuse
        if random.random() < 0.3:
            tags.append('reuse')
        
        # 10% khả năng có tag new
        if random.random() < 0.1:
            tags.append('new')
        
        return ','.join(tags) if tags else None
    
    def check_existing_data(self):
        """Kiểm tra dữ liệu CoinJoin hiện có"""
        self.stdout.write("Checking existing CoinJoin data...")
        
        # Đếm giao dịch CoinJoin
        coinjoin_txs = Transaction.objects.filter(tags__contains='coinjoin')
        self.stdout.write(f"Found {coinjoin_txs.count()} CoinJoin transactions")
        
        # Đếm địa chỉ liên quan
        coinjoin_addresses = Address.objects.filter(
            received_txos__transaction__tags__contains='coinjoin'
        ).distinct()
        self.stdout.write(f"Found {coinjoin_addresses.count()} addresses related to CoinJoin")
        
        # Thống kê tags
        tag_stats = {}
        for addr in Address.objects.all():
            if addr.tags:
                for tag in addr.tags.split(','):
                    tag = tag.strip()
                    if tag:
                        tag_stats[tag] = tag_stats.get(tag, 0) + 1
        
        self.stdout.write("Tag statistics:")
        for tag, count in sorted(tag_stats.items()):
            self.stdout.write(f"  {tag}: {count}")
        
        # Hiển thị một số giao dịch CoinJoin mẫu
        if coinjoin_txs.exists():
            self.stdout.write("\nSample CoinJoin transactions:")
            for tx in coinjoin_txs[:5]:
                self.stdout.write(f"  {tx.hash[:16]}... - {tx.inputs.count()} inputs, {tx.outputs.count()} outputs")
        
        self.stdout.write(self.style.SUCCESS("Data check complete!")) 