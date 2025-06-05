from django.core.management.base import BaseCommand
from bitcoin.models import Transaction, TxOutput, Address, TxInput
from django.db.models import Sum, Count, Q, F
from django.db import transaction as db_transaction
from django.utils import timezone
import logging
from decimal import Decimal
import statistics

logger = logging.getLogger(__name__)

# --- ĐỊNH NGHĨA NGƯỠNG ---
SATOSHI_PER_BTC = Decimal('100000000')

# Giá trị giao dịch
LARGE_VALUE_THRESHOLD = 1 * SATOSHI_PER_BTC
VERY_LARGE_VALUE_THRESHOLD = 10 * SATOSHI_PER_BTC

# Số lượng đầu vào/đầu ra
HIGH_IO_THRESHOLD = 10
VERY_HIGH_IO_THRESHOLD = 50

# Phí giao dịch
HIGH_FEE_THRESHOLD = Decimal('500000')  # 0.005 BTC
LOW_FEE_THRESHOLD = Decimal('500')      # 500 satoshi
HIGH_FEE_PER_BYTE_THRESHOLD = Decimal('50')  # satoshi/byte
LOW_FEE_PER_BYTE_THRESHOLD = Decimal('1')    # satoshi/byte

# Tái sử dụng địa chỉ
ADDRESS_REUSE_THRESHOLD = 10
HIGH_ADDRESS_REUSE_THRESHOLD = 50

# Peeling Chain
PEELING_SMALL_OUTPUT_RATIO = Decimal('0.1')

# Dust Output
DUST_OUTPUT_THRESHOLD = Decimal('1000')

# CoinJoin
COINJOIN_VALUE_VARIANCE = Decimal('0.05')  # ±5% giá trị đầu ra

# Temporal Analysis
HIGH_FREQUENCY_THRESHOLD = 10  # Số giao dịch/giờ
TIME_WINDOW_HOURS = 1

def add_tag(obj, tag_to_add):
    """Hàm trợ giúp để thêm tag mà không trùng lặp và trả về True nếu có thay đổi."""
    current_tags = set(obj.tags.split(',') if obj.tags else [])
    if tag_to_add not in current_tags:
        current_tags.add(tag_to_add)
        obj.tags = ','.join(filter(None, current_tags))
        return True
    return False

class Command(BaseCommand):
    help = 'Analyzes transactions and addresses for anomalies and applies tags.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full-rescan',
            action='store_true',
            help='Rescan all transactions and addresses instead of just untagged ones.',
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

    def process_chunk(self, transactions_chunk, addresses_chunk):
        """Xử lý một lô giao dịch và địa chỉ."""
        tx_update_list = []
        addr_update_list = []

        tx_hashes = [tx.hash for tx in transactions_chunk]
        addr_strings = [addr.address for addr in addresses_chunk]

        # Lấy dữ liệu liên quan hiệu quả hơn
        transactions = Transaction.objects.filter(hash__in=tx_hashes)\
            .prefetch_related('inputs', 'outputs', 'outputs__address', 'inputs__address')
        addresses = Address.objects.filter(address__in=addr_strings)

        tx_map = {tx.hash: tx for tx in transactions}
        addr_map = {addr.address: addr for addr in addresses}

        # --- PHÂN TÍCH GIAO DỊCH ---
        self.stdout.write(f"Analyzing {len(tx_map)} transactions...")
        for tx_hash, tx in tx_map.items():
            changed = False
            current_score = tx.anomaly_score

            # Lấy inputs/outputs từ prefetch
            inputs = list(tx.inputs.all())
            outputs = list(tx.outputs.all())

            # 1. Giao dịch giá trị lớn
            total_out = sum(o.value for o in outputs)
            tx.total_output_value = total_out
            if total_out >= VERY_LARGE_VALUE_THRESHOLD:
                changed |= add_tag(tx, 'very_large_value')
                tx.anomaly_score += 2.0
            elif total_out >= LARGE_VALUE_THRESHOLD:
                changed |= add_tag(tx, 'large_value')
                tx.anomaly_score += 1.0

            # 2. Nhiều Đầu vào/Đầu ra
            vin_count = len(inputs)
            vout_count = len(outputs)
            if vin_count >= VERY_HIGH_IO_THRESHOLD or vout_count >= VERY_HIGH_IO_THRESHOLD:
                changed |= add_tag(tx, 'very_high_io')
                tx.anomaly_score += 2.0
            elif vin_count >= HIGH_IO_THRESHOLD or vout_count >= HIGH_IO_THRESHOLD:
                changed |= add_tag(tx, 'high_io')
                tx.anomaly_score += 1.0

            # 3. Phí Bất thường
            if tx.fee >= HIGH_FEE_THRESHOLD:
                changed |= add_tag(tx, 'high_fee')
                tx.anomaly_score += 0.5
            if 0 < tx.fee <= LOW_FEE_THRESHOLD:
                changed |= add_tag(tx, 'low_fee')
                tx.anomaly_score += 0.5
            # Phí trên mỗi byte
            fee_per_byte = Decimal(tx.fee) / Decimal(tx.size) if tx.size > 0 else Decimal('0')
            if fee_per_byte >= HIGH_FEE_PER_BYTE_THRESHOLD:
                changed |= add_tag(tx, 'high_fee_per_byte')
                tx.anomaly_score += 0.7
            elif 0 < fee_per_byte <= LOW_FEE_PER_BYTE_THRESHOLD:
                changed |= add_tag(tx, 'low_fee_per_byte')
                tx.anomaly_score += 0.3
            # Phí cao so với giá trị
            if total_out > 0 and (Decimal(tx.fee) / Decimal(total_out)) > Decimal('0.1'):
                changed |= add_tag(tx, 'high_fee_ratio')
                tx.anomaly_score += 1.5

            # 4. Coinbase
            if tx.is_coinbase:
                changed |= add_tag(tx, 'coinbase')

            # 5. Peeling Chain (Cải tiến)
            if (1 <= vin_count <= 2) and vout_count == 2:
                outputs_sorted = sorted(outputs, key=lambda o: o.value, reverse=True)
                large_out, small_out = outputs_sorted[0], outputs_sorted[1]
                if large_out.value > 0 and (Decimal(small_out.value) / Decimal(large_out.value)) < PEELING_SMALL_OUTPUT_RATIO:
                    # Kiểm tra xem large_out có liên quan đến input không
                    input_addresses = {inp.address.address for inp in inputs if inp.address}
                    if large_out.address and large_out.address.address not in input_addresses:
                        changed |= add_tag(tx, 'peeling_chain')
                        tx.anomaly_score += 1.5

            # 6. Giao dịch Tập trung (Consolidation)
            if vin_count >= HIGH_IO_THRESHOLD and vout_count <= 2:
                changed |= add_tag(tx, 'consolidation')
                tx.anomaly_score += 1.0

            # 7. Giao dịch Phân tán (Fan-out)
            if vin_count <= 2 and vout_count >= HIGH_IO_THRESHOLD:
                changed |= add_tag(tx, 'fan_out')
                tx.anomaly_score += 1.0

            # 8. Dust Output
            if any(o.value <= DUST_OUTPUT_THRESHOLD for o in outputs):
                changed |= add_tag(tx, 'dust_output')
                tx.anomaly_score += 0.2

            # 9. Sử dụng nhiều địa chỉ Input
            input_addresses = {inp.address.address for inp in inputs if inp.address}
            if len(input_addresses) > 1:
                changed |= add_tag(tx, 'multi_input_addr')
                tx.anomaly_score += 0.5 * (len(input_addresses) - 1)

            # 10. CoinJoin Detection
            if vin_count >= HIGH_IO_THRESHOLD and vout_count >= HIGH_IO_THRESHOLD:
                output_values = [o.value for o in outputs if o.value > 0]
                if output_values:
                    mean_value = statistics.mean(output_values)
                    if all(abs(Decimal(o.value) - Decimal(mean_value)) / Decimal(mean_value) <= COINJOIN_VALUE_VARIANCE for o in outputs):
                        changed |= add_tag(tx, 'coinjoin')
                        tx.anomaly_score += 2.0

            # 11. SegWit Usage
            if any(o.script_pub_key.startswith(('0014', '0020')) for o in outputs):
                changed |= add_tag(tx, 'segwit')
                tx.anomaly_score += 0.1  # Ít đáng ngờ, chỉ để theo dõi

            # 12. RBF Enabled
            if any(inp.sequence < 0xFFFFFFFF for inp in inputs):
                changed |= add_tag(tx, 'rbf_enabled')
                tx.anomaly_score += 0.3

            # Chuẩn hóa anomaly_score
            tx.anomaly_score = round(tx.anomaly_score, 2)
            tx.anomaly_score = min(tx.anomaly_score, 10.0)

            if changed or tx.anomaly_score != current_score:
                tx_update_list.append(tx)

        # --- PHÂN TÍCH ĐỊA CHỈ ---
        self.stdout.write(f"Analyzing {len(addr_map)} addresses...")
        for addr_str, addr in addr_map.items():
            changed = False
            # Cập nhật tx_count
            if addr.tx_count == 0:
                input_count = TxInput.objects.filter(address=addr).count()
                output_count = TxOutput.objects.filter(address=addr).count()
                addr.tx_count = input_count + output_count
                changed = True

            # 1. Địa chỉ tái sử dụng
            if addr.tx_count >= HIGH_ADDRESS_REUSE_THRESHOLD:
                changed |= add_tag(addr, 'high_reuse')
            elif addr.tx_count >= ADDRESS_REUSE_THRESHOLD:
                changed |= add_tag(addr, 'reuse')

            # 2. Địa chỉ mới
            if addr.tx_count == 1:
                changed |= add_tag(addr, 'new')

            # 3. Hoạt động tần suất cao
            recent_txs = Transaction.objects.filter(
                Q(inputs__address=addr) | Q(outputs__address=addr),
                time__gte=timezone.now() - timezone.timedelta(hours=TIME_WINDOW_HOURS)
            ).distinct().count()
            if recent_txs >= HIGH_FREQUENCY_THRESHOLD:
                changed |= add_tag(addr, 'high_frequency')
                # Không tăng anomaly_score cho địa chỉ, vì đã xử lý ở giao dịch

            if changed:
                addr_update_list.append(addr)

        # --- CẬP NHẬT DATABASE (BULK) ---
        if tx_update_list:
            Transaction.objects.bulk_update(
                tx_update_list,
                ['tags', 'anomaly_score', 'total_output_value'],
                batch_size=500
            )
            self.stdout.write(f"Updated {len(tx_update_list)} transactions.")
        if addr_update_list:
            Address.objects.bulk_update(
                addr_update_list,
                ['tags', 'tx_count'],
                batch_size=1000
            )
            self.stdout.write(f"Updated {len(addr_update_list)} addresses.")

    @db_transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Starting analysis...")

        full_rescan = kwargs['full_rescan']
        chunk_size = kwargs['chunk_size']
        start_block = kwargs.get('start_block')

        # Lọc giao dịch và địa chỉ
        if full_rescan:
            self.stdout.write("Performing a full rescan...")
            transaction_queryset = Transaction.objects.all()
            address_queryset = Address.objects.all()
        else:
            self.stdout.write("Analyzing new/untagged items...")
            transaction_queryset = Transaction.objects.filter(
                Q(tags__isnull=True) | Q(anomaly_score=0.0)
            )
            address_queryset = Address.objects.filter(Q(tags__isnull=True))

        if start_block:
            transaction_queryset = transaction_queryset.filter(block__height__gte=start_block)

        tx_count = transaction_queryset.count()
        addr_count = address_queryset.count()
        self.stdout.write(f"Found {tx_count} transactions and {addr_count} addresses to analyze.")

        # Xử lý theo lô
        for i in range(0, tx_count, chunk_size):
            tx_chunk = list(transaction_queryset[i:i + chunk_size])
            related_addr_set = set()
            for tx in tx_chunk:
                for inp in tx.inputs.all():
                    if inp.address:
                        related_addr_set.add(inp.address.address)
                for out in tx.outputs.all():
                    if out.address:
                        related_addr_set.add(out.address.address)

            addr_chunk = list(address_queryset.filter(address__in=related_addr_set))
            self.stdout.write(f"Processing chunk {i//chunk_size + 1}...")
            self.process_chunk(tx_chunk, addr_chunk)

        # Xử lý địa chỉ còn lại
        if not full_rescan:
            self.stdout.write("Processing remaining addresses...")
            for i in range(0, addr_count, chunk_size * 2):
                addr_chunk = list(address_queryset[i:i + (chunk_size * 2)])
                self.process_chunk([], addr_chunk)

        self.stdout.write(self.style.SUCCESS("Analysis complete."))