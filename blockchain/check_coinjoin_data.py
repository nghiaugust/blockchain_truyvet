#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain.settings')
django.setup()

from bitcoin.models import Address, Transaction, TxInput, TxOutput, Block

def check_coinjoin_data():
    """Kiểm tra dữ liệu CoinJoin thực tế"""
    print("=== Kiểm tra dữ liệu CoinJoin thực tế ===")
    
    # Kiểm tra giao dịch có tag coinjoin
    coinjoin_txs_by_tag = Transaction.objects.filter(tags__contains='coinjoin')
    print(f"Số giao dịch có tag 'coinjoin': {coinjoin_txs_by_tag.count()}")
    
    if coinjoin_txs_by_tag.exists():
        print("Các giao dịch có tag coinjoin:")
        for tx in coinjoin_txs_by_tag[:5]:
            print(f"  - {tx.hash[:16]}... - {tx.inputs.count()} inputs, {tx.outputs.count()} outputs")
        if coinjoin_txs_by_tag.count() > 5:
            print(f"  ... và {coinjoin_txs_by_tag.count() - 5} giao dịch khác")
    
    # Kiểm tra giao dịch có nhiều input/output (có thể là CoinJoin)
    high_io_txs = Transaction.objects.filter(
        vin_sz__gte=5,  # Ít nhất 5 inputs
        vout_sz__gte=5   # Ít nhất 5 outputs
    ).order_by('-vin_sz', '-vout_sz')[:10]
    
    print(f"\nSố giao dịch có nhiều I/O (>=5): {high_io_txs.count()}")
    if high_io_txs.exists():
        print("Các giao dịch có nhiều I/O:")
        for tx in high_io_txs[:5]:
            print(f"  - {tx.hash[:16]}... - {tx.vin_sz} inputs, {tx.vout_sz} outputs (tags: {tx.tags or 'None'})")
    
    # Kiểm tra địa chỉ có tag coinjoin
    coinjoin_addresses = Address.objects.filter(tags__contains='coinjoin')
    print(f"\nSố địa chỉ có tag 'coinjoin': {coinjoin_addresses.count()}")
    
    if coinjoin_addresses.exists():
        print("Các địa chỉ có tag coinjoin:")
        for addr in coinjoin_addresses[:5]:
            print(f"  - {addr.address} (tags: {addr.tags})")
        if coinjoin_addresses.count() > 5:
            print(f"  ... và {coinjoin_addresses.count() - 5} địa chỉ khác")
    
    # Kiểm tra giao dịch có anomaly_score cao (có thể là CoinJoin)
    high_anomaly_txs = Transaction.objects.filter(
        anomaly_score__gte=5.0
    ).order_by('-anomaly_score')[:10]
    
    print(f"\nSố giao dịch có anomaly_score cao (>=5.0): {high_anomaly_txs.count()}")
    if high_anomaly_txs.exists():
        print("Các giao dịch có anomaly_score cao:")
        for tx in high_anomaly_txs[:5]:
            print(f"  - {tx.hash[:16]}... - score: {tx.anomaly_score:.2f} (tags: {tx.tags or 'None'})")
    
    # Kiểm tra giao dịch có giá trị output đồng đều (đặc trưng của CoinJoin)
    print(f"\n=== Phân tích giá trị output ===")
    sample_txs = Transaction.objects.all()[:100]
    uniform_value_txs = []
    
    for tx in sample_txs:
        outputs = tx.outputs.all()
        if outputs.count() >= 3:  # Ít nhất 3 outputs
            values = [o.value for o in outputs if o.value > 0]
            if len(values) >= 3:
                mean_value = sum(values) / len(values)
                variance = sum((v - mean_value) ** 2 for v in values) / len(values)
                uniformity = 1 - (variance / (mean_value ** 2)) if mean_value > 0 else 0
                
                if uniformity > 0.9:  # Độ đồng đều cao
                    uniform_value_txs.append({
                        'tx': tx,
                        'uniformity': uniformity,
                        'mean_value': mean_value,
                        'output_count': len(values)
                    })
    
    print(f"Số giao dịch có giá trị output đồng đều (uniformity > 0.9): {len(uniform_value_txs)}")
    if uniform_value_txs:
        print("Các giao dịch có giá trị output đồng đều:")
        for item in uniform_value_txs[:5]:
            tx = item['tx']
            print(f"  - {tx.hash[:16]}... - uniformity: {item['uniformity']:.3f}, outputs: {item['output_count']} (tags: {tx.tags or 'None'})")

if __name__ == '__main__':
    check_coinjoin_data() 