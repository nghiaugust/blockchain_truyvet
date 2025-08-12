#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain.settings')
django.setup()

from bitcoin.models import Address, Transaction, TxInput, TxOutput, Block

def check_sample_data():
    """Kiểm tra và xóa dữ liệu mẫu"""
    print("=== Kiểm tra dữ liệu mẫu ===")
    
    # Kiểm tra địa chỉ mẫu
    sample_addresses = Address.objects.filter(address__contains='SampleAddr')
    print(f"Số địa chỉ mẫu: {sample_addresses.count()}")
    
    if sample_addresses.exists():
        print("Các địa chỉ mẫu:")
        for addr in sample_addresses[:5]:
            print(f"  - {addr.address}")
        if sample_addresses.count() > 5:
            print(f"  ... và {sample_addresses.count() - 5} địa chỉ khác")
    
    # Kiểm tra giao dịch CoinJoin
    coinjoin_txs = Transaction.objects.filter(tags__contains='coinjoin')
    print(f"\nSố giao dịch CoinJoin: {coinjoin_txs.count()}")
    
    if coinjoin_txs.exists():
        print("Các giao dịch CoinJoin:")
        for tx in coinjoin_txs[:5]:
            print(f"  - {tx.hash[:16]}... - {tx.inputs.count()} inputs, {tx.outputs.count()} outputs")
        if coinjoin_txs.count() > 5:
            print(f"  ... và {coinjoin_txs.count() - 5} giao dịch khác")
    
    # Kiểm tra block mẫu
    sample_blocks = Block.objects.filter(hash__startswith='0000000000000000000000000000000000000000000000000000000000000000')
    print(f"\nSố block mẫu: {sample_blocks.count()}")
    
    return sample_addresses.count() > 0 or sample_blocks.count() > 0

def clean_sample_data():
    """Xóa dữ liệu mẫu"""
    print("\n=== Xóa dữ liệu mẫu ===")
    
    # Xóa các giao dịch liên quan đến địa chỉ mẫu
    sample_addresses = Address.objects.filter(address__contains='SampleAddr')
    sample_txs = Transaction.objects.filter(
        inputs__address__in=sample_addresses
    ).distinct()
    
    print(f"Xóa {sample_txs.count()} giao dịch liên quan đến địa chỉ mẫu")
    sample_txs.delete()
    
    # Xóa các địa chỉ mẫu
    print(f"Xóa {sample_addresses.count()} địa chỉ mẫu")
    sample_addresses.delete()
    
    # Xóa block mẫu
    sample_blocks = Block.objects.filter(hash__startswith='0000000000000000000000000000000000000000000000000000000000000000')
    print(f"Xóa {sample_blocks.count()} block mẫu")
    sample_blocks.delete()
    
    print("Đã xóa xong dữ liệu mẫu!")

def check_real_data():
    """Kiểm tra dữ liệu thực"""
    print("\n=== Kiểm tra dữ liệu thực ===")
    
    total_addresses = Address.objects.count()
    total_transactions = Transaction.objects.count()
    total_blocks = Block.objects.count()
    
    print(f"Tổng số địa chỉ: {total_addresses}")
    print(f"Tổng số giao dịch: {total_transactions}")
    print(f"Tổng số block: {total_blocks}")
    
    # Kiểm tra các địa chỉ có tag coinjoin
    coinjoin_addresses = Address.objects.filter(tags__contains='coinjoin')
    print(f"Số địa chỉ có tag coinjoin: {coinjoin_addresses.count()}")
    
    if coinjoin_addresses.exists():
        print("Các địa chỉ có tag coinjoin:")
        for addr in coinjoin_addresses[:10]:
            print(f"  - {addr.address} (tags: {addr.tags})")
        if coinjoin_addresses.count() > 10:
            print(f"  ... và {coinjoin_addresses.count() - 10} địa chỉ khác")

if __name__ == '__main__':
    has_sample_data = check_sample_data()
    
    if has_sample_data:
        response = input("\nCó dữ liệu mẫu. Bạn có muốn xóa không? (y/n): ")
        if response.lower() == 'y':
            clean_sample_data()
            check_real_data()
        else:
            print("Không xóa dữ liệu mẫu.")
    else:
        print("\nKhông có dữ liệu mẫu.")
        check_real_data() 