import json
import os
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction, IntegrityError
from bitcoin.models import Block, Transaction, Address, TxInput, TxOutput

class Command(BaseCommand):
    help = 'Import Bitcoin block data from a JSON file into the database using new models.'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='The path to the JSON file to import.')

    def handle(self, *args, **kwargs):
        json_path = kwargs['json_file']

        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f'File {json_path} not found'))
            return

        self.stdout.write(f'Starting import from {json_path}...')

        try:
            with open(json_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading JSON file: {str(e)}'))
            return

        # Kiểm tra cấu trúc JSON và xử lý
        if 'blocks' in data:
            # Trường hợp có bọc ngoài với key "blocks"
            blocks_data = data['blocks']
            self.stdout.write(f'Found {len(blocks_data)} blocks in the file.')
            
            for block_data in blocks_data:
                self._process_single_block(block_data)
        else:
            # Trường hợp JSON trực tiếp là một block
            self.stdout.write('Processing single block...')
            self._process_single_block(data)

    @transaction.atomic # Đảm bảo toàn bộ khối được nhập hoặc không gì cả
    def _process_single_block(self, block_data):
        try:
            # 1. Tạo hoặc lấy Block
            block_time = datetime.fromtimestamp(block_data.get('time', 0), tz=timezone.utc)
            block, created = Block.objects.get_or_create(
                hash=block_data['hash'],
                defaults={
                    'height': block_data['height'],
                    'time': block_time,
                    'n_tx': block_data['n_tx'],
                    'fee': block_data['fee'],
                }
            )
            if not created:
                self.stdout.write(self.style.WARNING(f'Block {block.height} already exists. Skipping.'))
                return

            self.stdout.write(f'Processing Block {block.height}...')

            all_addresses = set()
            transactions_data = block_data.get('tx', [])
            
            tx_to_create = []
            inputs_to_create = []
            outputs_to_create = []
            
            # Bản đồ để liên kết TxOutput với TxInput sau này
            outputs_to_update_spent_status = {} # (prev_tx_hash, prev_output_index) -> (spending_tx_hash, spending_input_index)

            # Thu thập tất cả địa chỉ trước
            for tx_json in transactions_data:
                for inp in tx_json.get('inputs', []):
                    if 'prev_out' in inp and 'addr' in inp['prev_out']:
                        all_addresses.add(inp['prev_out']['addr'])
                for out in tx_json.get('out', []):
                    if 'addr' in out:
                        all_addresses.add(out['addr'])

            # 2. Bulk Create Addresses (bỏ qua nếu đã tồn tại)
            existing_addresses = set(Address.objects.filter(address__in=all_addresses).values_list('address', flat=True))
            new_addresses = [Address(address=addr) for addr in all_addresses if addr not in existing_addresses]
            if new_addresses:
                Address.objects.bulk_create(new_addresses, ignore_conflicts=True)
                self.stdout.write(f'Created {len(new_addresses)} new addresses.')

            # Tải tất cả địa chỉ cần thiết vào bộ nhớ để gán FK
            address_map = {addr.address: addr for addr in Address.objects.filter(address__in=all_addresses)}
            self.stdout.write(f'Loaded {len(address_map)} addresses into memory.')

            # 3. Chuẩn bị dữ liệu Transaction, Input, Output
            for tx_json in transactions_data:
                tx_hash = tx_json['hash']
                tx_time = datetime.fromtimestamp(tx_json.get('time', block.time.timestamp()), tz=timezone.utc)
                is_coinbase = not tx_json.get('inputs', [{}])[0].get('prev_out')

                tx_obj = Transaction(
                    hash=tx_hash,
                    block=block,
                    tx_index=tx_json['tx_index'],
                    time=tx_time,
                    fee=tx_json.get('fee', 0),
                    vin_sz=tx_json['vin_sz'],
                    vout_sz=tx_json['vout_sz'],
                    size=tx_json['size'],
                    weight=tx_json['weight'],
                    lock_time=tx_json['lock_time'],
                    is_coinbase=is_coinbase,
                )
                tx_to_create.append(tx_obj)

                # Inputs
                for i, inp_json in enumerate(tx_json.get('inputs', [])):
                    prev_out = inp_json.get('prev_out')
                    addr_obj = None
                    prev_tx_hash = None
                    prev_output_index = None
                    prev_value = None

                    if prev_out:
                        prev_tx_hash = prev_out.get('tx_index') # Dùng tx_index để tìm hash sau
                        prev_output_index = prev_out.get('n')
                        prev_value = prev_out.get('value')
                        addr_str = prev_out.get('addr')
                        if addr_str:
                           addr_obj = address_map.get(addr_str)
                        # Đánh dấu UTXO tương ứng sẽ được chi tiêu
                        if prev_tx_hash and prev_output_index is not None:
                           outputs_to_update_spent_status[(prev_tx_hash, prev_output_index)] = (tx_hash, i)
                    
                    inputs_to_create.append(TxInput(
                        transaction=tx_obj, # Sẽ gán sau khi Transaction được tạo
                        input_index=i,
                        prev_tx_hash=prev_tx_hash,
                        prev_output_index=prev_output_index,
                        prev_value=prev_value,
                        address=addr_obj,
                        sequence=inp_json.get('sequence', 0),
                    ))

                # Outputs
                for o, out_json in enumerate(tx_json.get('out', [])):
                    addr_str = out_json.get('addr')
                    addr_obj = address_map.get(addr_str) if addr_str else None
                    
                    outputs_to_create.append(TxOutput(
                        transaction=tx_obj, # Sẽ gán sau khi Transaction được tạo
                        output_index=o,
                        value=out_json['value'],
                        address=addr_obj,
                        script_pub_key=out_json.get('script', ''),
                        is_spent=out_json.get('spent', False), # Dùng tạm giá trị từ API
                    ))
            
            # 4. Bulk Create Transactions
            Transaction.objects.bulk_create(tx_to_create, batch_size=500)
            self.stdout.write(f'Created {len(tx_to_create)} transactions.')

            # Tải Transaction vừa tạo vào map để gán FK
            tx_map = {tx.hash: tx for tx in Transaction.objects.filter(block=block)}
            self.stdout.write(f'Loaded {len(tx_map)} transactions into memory.')
            
            # Cập nhật FK cho Inputs và Outputs
            for inp in inputs_to_create:
                inp.transaction = tx_map[inp.transaction.hash] # Gán đối tượng Transaction đã lưu
                
            for out in outputs_to_create:
                out.transaction = tx_map[out.transaction.hash] # Gán đối tượng Transaction đã lưu

            # 5. Bulk Create Inputs & Outputs
            TxInput.objects.bulk_create(inputs_to_create, batch_size=1000)
            TxOutput.objects.bulk_create(outputs_to_create, batch_size=1000)
            self.stdout.write(f'Created {len(inputs_to_create)} inputs and {len(outputs_to_create)} outputs.')

            # 6. Cập nhật trạng thái 'is_spent' (Bước Nâng cao)
            tx_index_to_hash_map = {tx.tx_index: tx.hash for tx in tx_map.values()}
            
            outputs_to_update_ids = []
            updates_info = {} # id -> (spending_tx_hash, spending_input_index)

            # Tìm các TxOutput cần update trong DB
            outputs_to_find = []
            for (prev_tx_idx, prev_out_idx), (spending_hash, spending_idx) in outputs_to_update_spent_status.items():
                prev_hash = tx_index_to_hash_map.get(prev_tx_idx)
                if prev_hash: # Chỉ xử lý nếu prev_tx nằm trong khối này
                    outputs_to_find.append((prev_hash, prev_out_idx))
                    updates_info[(prev_hash, prev_out_idx)] = (spending_hash, spending_idx)

            if outputs_to_find:
                # Xây dựng Q objects để tìm kiếm
                from django.db.models import Q
                query = Q()
                for hash_val, index_val in outputs_to_find:
                    query |= Q(transaction__hash=hash_val, output_index=index_val)
                
                outputs_found = TxOutput.objects.filter(query)

                for output in outputs_found:
                    spending_hash, spending_idx = updates_info.get((output.transaction.hash, output.output_index))
                    output.is_spent = True
                    output.spending_tx_hash = spending_hash
                    output.spending_input_index = spending_idx
                
                TxOutput.objects.bulk_update(outputs_found, ['is_spent', 'spending_tx_hash', 'spending_input_index'], batch_size=500)
                self.stdout.write(f'Updated {len(outputs_found)} outputs spent within the block.')

            self.stdout.write(self.style.SUCCESS(f'Successfully imported all data for block {block.height}'))

        except IntegrityError as e:
            self.stdout.write(self.style.ERROR(f'Database Integrity Error: {str(e)}. Might indicate data already exists or inconsistency.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An unexpected error occurred: {str(e)}'))
            # Cần có cơ chế log lỗi chi tiết hơn ở đây
            raise # Ném lại lỗi để transaction rollback