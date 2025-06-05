from django.db import models
from django.utils import timezone
import datetime

class Block(models.Model):
    """
    Lưu trữ thông tin cơ bản về mỗi khối.
    """
    hash = models.CharField(max_length=64, primary_key=True, help_text="Mã hash của khối")
    height = models.PositiveIntegerField(unique=True, db_index=True, help_text="Chiều cao của khối")
    time = models.DateTimeField(db_index=True, help_text="Thời gian khối được tạo (UTC)")
    n_tx = models.PositiveIntegerField(help_text="Số lượng giao dịch trong khối")
    fee = models.PositiveBigIntegerField(help_text="Tổng phí giao dịch trong khối (satoshi)")
    # Các trường khác bạn có thể muốn thêm: ver, prev_block, mrkl_root, bits, nonce, size...

    def __str__(self):
        return f"Block {self.height} ({self.hash[:8]}...)"

    class Meta:
        ordering = ['-height']
        verbose_name = "Khối"
        verbose_name_plural = "Các khối"

class AddressCluster(models.Model):
    """
    Lưu trữ thông tin về các cụm địa chỉ (address clusters).
    """
    cluster_id = models.CharField(max_length=64, primary_key=True, help_text="ID duy nhất của cụm địa chỉ")
    address_count = models.PositiveIntegerField(default=1, help_text="Số lượng địa chỉ trong cụm")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Thời gian tạo cụm")
    updated_at = models.DateTimeField(auto_now=True, help_text="Thời gian cập nhật cụm")
    notes = models.TextField(blank=True, null=True, help_text="Ghi chú về cụm (ví dụ: sàn giao dịch, ví cá nhân)")

    def __str__(self):
        return f"Cluster {self.cluster_id} ({self.address_count} addresses)"

    class Meta:
        verbose_name = "Cụm Địa chỉ"
        verbose_name_plural = "Các cụm Địa chỉ"
        
class Address(models.Model):
    """
    Lưu trữ các địa chỉ Bitcoin duy nhất và các thông tin liên quan.
    """
    address = models.CharField(max_length=128, primary_key=True, help_text="Địa chỉ Bitcoin")
    first_seen = models.DateTimeField(auto_now_add=True, help_text="Lần đầu tiên địa chỉ xuất hiện")
    last_seen = models.DateTimeField(auto_now=True, help_text="Lần cuối địa chỉ xuất hiện")
    # Các trường để đánh dấu và phân tích:
    is_exchange = models.BooleanField(default=False, db_index=True, help_text="Là địa chỉ sàn giao dịch?")
    tags = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Nhãn đánh dấu (ví dụ: 'scam', 'mixing', 'whale')")
    tx_count = models.PositiveIntegerField(default=0, db_index=True, help_text="Số lượng giao dịch liên quan")
    cluster = models.ForeignKey(
        AddressCluster, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='addresses', 
        db_index=True, 
        help_text="Cụm địa chỉ mà địa chỉ này thuộc về"
    )
    def __str__(self):
        return self.address

    class Meta:
        verbose_name = "Địa chỉ"
        verbose_name_plural = "Các địa chỉ"


class Transaction(models.Model):
    """
    Lưu trữ thông tin chi tiết về mỗi giao dịch.
    """
    hash = models.CharField(max_length=64, primary_key=True, help_text="Mã hash (TxID) của giao dịch")
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='transactions', db_index=True, help_text="Khối chứa giao dịch")
    tx_index = models.PositiveBigIntegerField(unique=True, db_index=True, help_text="Chỉ số giao dịch (từ Blockchain.com API)")
    time = models.DateTimeField(db_index=True, help_text="Thời gian giao dịch (UTC)")
    fee = models.PositiveBigIntegerField(help_text="Phí giao dịch (satoshi)")
    vin_sz = models.PositiveSmallIntegerField(help_text="Số lượng đầu vào")
    vout_sz = models.PositiveSmallIntegerField(help_text="Số lượng đầu ra")
    size = models.PositiveIntegerField(help_text="Kích thước giao dịch (bytes)")
    weight = models.PositiveIntegerField(help_text="Trọng lượng giao dịch (WU)")
    lock_time = models.PositiveIntegerField(help_text="Lock time của giao dịch")
    is_coinbase = models.BooleanField(default=False, help_text="Là giao dịch coinbase?")
    # Các trường để đánh dấu:
    anomaly_score = models.FloatField(default=0.0, db_index=True, help_text="Điểm bất thường (tính toán sau)")
    notes = models.TextField(blank=True, null=True, help_text="Ghi chú phân tích")
    total_output_value = models.PositiveBigIntegerField(default=0, help_text="Tổng giá trị đầu ra (satoshi)")
    tags = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text="Các nhãn (phân tách bởi dấu phẩy, ví dụ: large_value, high_fee, mixing, peeling)")

    def __str__(self):
        return f"Tx {self.hash[:8]}..."

    class Meta:
        ordering = ['-time']
        verbose_name = "Giao dịch"
        verbose_name_plural = "Các giao dịch"
        # Chỉ mục kết hợp tx_index và hash (mặc dù hash là PK) để hỗ trợ tra cứu kép
        indexes = [
            models.Index(fields=['tx_index', 'hash']),
        ]

class TxInput(models.Model):
    """
    Lưu trữ thông tin về một đầu vào cụ thể của giao dịch.
    """
    id = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='inputs', db_index=True, help_text="Giao dịch chứa đầu vào này")
    input_index = models.PositiveSmallIntegerField(help_text="Thứ tự của đầu vào trong giao dịch")
    # Liên kết đến đầu ra trước đó (UTXO)
    prev_tx_hash = models.CharField(max_length=64, db_index=True, null=True, blank=True, help_text="Hash của giao dịch trước (null nếu coinbase)")
    prev_output_index = models.PositiveIntegerField(null=True, blank=True, help_text="Chỉ số đầu ra của giao dịch trước (null nếu coinbase)")
    # Thông tin về đầu ra trước đó (được sao chép để truy vấn nhanh hơn)
    prev_value = models.PositiveBigIntegerField(null=True, blank=True, help_text="Giá trị của UTXO được chi tiêu")
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, related_name='spent_txos', null=True, db_index=True, help_text="Địa chỉ sở hữu UTXO")
    sequence = models.BigIntegerField()

    def __str__(self):
        return f"Input {self.input_index} for Tx {self.transaction.hash[:8]}..."

    class Meta:
        unique_together = ('transaction', 'input_index') # Mỗi input trong 1 tx là duy nhất
        ordering = ['transaction', 'input_index']
        verbose_name = "Đầu vào Giao dịch"
        verbose_name_plural = "Các đầu vào Giao dịch"
        indexes = [
            models.Index(fields=['prev_tx_hash', 'prev_output_index']), # Quan trọng để truy vết ngược
        ]

class TxOutput(models.Model):
    """
    Lưu trữ thông tin về một đầu ra cụ thể (UTXO) của giao dịch.
    """
    id = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='outputs', db_index=True, help_text="Giao dịch tạo ra đầu ra này")
    output_index = models.PositiveSmallIntegerField(help_text="Thứ tự của đầu ra trong giao dịch")
    value = models.PositiveBigIntegerField(help_text="Giá trị của đầu ra (satoshi)")
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, related_name='received_txos', null=True, db_index=True, help_text="Địa chỉ nhận đầu ra")
    script_pub_key = models.TextField(help_text="Script khóa (scriptPubKey)")
    # Thông tin về việc đã được chi tiêu hay chưa
    is_spent = models.BooleanField(default=False, db_index=True, help_text="Đầu ra này đã được chi tiêu chưa?")
    spending_tx_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True, help_text="Hash của giao dịch chi tiêu đầu ra này")
    spending_input_index = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Chỉ số đầu vào chi tiêu đầu ra này")

    def __str__(self):
        return f"Output {self.output_index} for Tx {self.transaction.hash[:8]}... ({self.value} sats)"

    class Meta:
        unique_together = ('transaction', 'output_index') # Mỗi output trong 1 tx là duy nhất
        ordering = ['transaction', 'output_index']
        verbose_name = "Đầu ra Giao dịch (UTXO)"
        verbose_name_plural = "Các đầu ra Giao dịch (UTXOs)"
        indexes = [
            # Chỉ mục này rất quan trọng để tìm UTXO dựa trên TxID và N
            models.Index(fields=['transaction', 'output_index']),
            # Chỉ mục để tìm UTXO chưa chi tiêu của một địa chỉ
            models.Index(fields=['address', 'is_spent']),
        ]