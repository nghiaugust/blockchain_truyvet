from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.core.management import call_command
from django.db import transaction, IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from bitcoin.models import Block, Transaction, Address, TxInput, TxOutput
import requests
import json
import logging
from datetime import datetime, timezone as dt_timezone
from io import StringIO
import sys

logger = logging.getLogger(__name__)

def import_data_view(request):
    """View chính để hiển thị form import và danh sách blocks"""
    blocks = Block.objects.all().order_by('-height')[:20]  # Hiển thị 20 block gần nhất
    
    context = {
        'blocks': blocks,
        'total_blocks': Block.objects.count(),
    }
    return render(request, 'import_data/import_data.html', context)

@csrf_exempt
def import_block_api(request):
    """API endpoint để import block từ blockchain.info"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Phương thức không được hỗ trợ'})
    
    try:
        data = json.loads(request.body)
        block_height = data.get('block_height')
        
        if not block_height:
            return JsonResponse({'success': False, 'message': 'Vui lòng nhập số khối'})
        
        # Chuyển đổi sang số nguyên
        try:
            block_height = int(block_height)
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Số khối phải là một số nguyên'})
        
        # Kiểm tra xem block đã tồn tại chưa
        if Block.objects.filter(height=block_height).exists():
            return JsonResponse({'success': False, 'message': f'Khối {block_height} đã tồn tại trong cơ sở dữ liệu'})
        
        # Bước 1: Gọi API blockchain.info
        try:
            api_url = f'https://blockchain.info/block-height/{block_height}?format=json'
            logger.info(f'Đang gọi API: {api_url}')
            
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            block_data = response.json()
            logger.info(f'API trả về thành công cho block {block_height}')
            
        except requests.exceptions.RequestException as e:
            logger.error(f'Lỗi khi gọi API: {str(e)}')
            return JsonResponse({'success': False, 'message': f'Lỗi khi gọi API blockchain.info: {str(e)}'})
        except json.JSONDecodeError as e:
            logger.error(f'Lỗi parse JSON: {str(e)}')
            return JsonResponse({'success': False, 'message': 'Dữ liệu trả về từ API không hợp lệ'})
          # Bước 2: Import dữ liệu vào database
        try:
            logger.info(f'Bắt đầu import dữ liệu cho block {block_height}')
            imported_blocks = _process_block_data(block_data)
            logger.info(f'Import thành công {len(imported_blocks)} khối: {imported_blocks}')
            
        except Exception as e:
            logger.error(f'Lỗi khi import dữ liệu: {str(e)}', exc_info=True)
            return JsonResponse({'success': False, 'message': f'Lỗi khi import dữ liệu: {str(e)}'})
          # Bước 3: Chạy phân tích heuristics
        try:
            logger.info(f'Bắt đầu chạy heuristics cho block {block_height}')
            
            # Capture output from management command
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = captured_output = StringIO()
            sys.stderr = captured_error = StringIO()
            
            call_command('heuristics', '--chunk-size=1000', f'--start-block={block_height}')
            
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            heuristics_output = captured_output.getvalue()
            heuristics_error = captured_error.getvalue()
            
            if heuristics_error:
                logger.warning(f'Heuristics stderr: {heuristics_error}')
            
            logger.info(f'Hoàn thành phân tích heuristics cho block {block_height}')
            logger.info(f'Heuristics output: {heuristics_output[:500]}...' if len(heuristics_output) > 500 else f'Heuristics output: {heuristics_output}')
            
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            logger.error(f'Lỗi khi chạy heuristics: {str(e)}')
            # Không return error, chỉ warning vì import đã thành công
            logger.warning(f'Import block {block_height} thành công nhưng heuristics bị lỗi: {str(e)}')
        
        # Lấy thông tin block vừa import
        imported_block_info = []
        for block_hash in imported_blocks:
            try:
                block = Block.objects.get(hash=block_hash)
                imported_block_info.append({
                    'height': block.height,
                    'hash': block.hash,
                    'time': block.time.strftime('%Y-%m-%d %H:%M:%S'),
                    'n_tx': block.n_tx
                })
            except Block.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True, 
            'message': f'Import thành công khối {block_height} và hoàn thành phân tích',
            'blocks': imported_block_info
        })
        
    except Exception as e:
        logger.error(f'Lỗi không mong muốn: {str(e)}')
        return JsonResponse({'success': False, 'message': f'Lỗi không mong muốn: {str(e)}'})

@transaction.atomic
def _process_block_data(data):
    """Xử lý dữ liệu block từ API (tương tự import_block_data command)"""
    imported_blocks = []
    
    try:
        # Kiểm tra cấu trúc JSON
        if 'blocks' in data:
            blocks_data = data['blocks']
            logger.info(f'Tìm thấy {len(blocks_data)} khối trong dữ liệu API')
            
            for block_data in blocks_data:
                block_hash = _process_single_block(block_data)
                if block_hash:
                    imported_blocks.append(block_hash)
        else:
            # Trường hợp JSON trực tiếp là một block
            logger.info('Xử lý khối đơn lẻ')
            block_hash = _process_single_block(data)
            if block_hash:
                imported_blocks.append(block_hash)
                
        return imported_blocks
        
    except Exception as e:
        logger.error(f'Lỗi khi xử lý dữ liệu block: {str(e)}')
        raise

def _process_single_block(block_data):
    """Xử lý một block đơn lẻ"""
    try:        # 1. Tạo Block
        block_time = datetime.fromtimestamp(block_data.get('time', 0), tz=dt_timezone.utc)
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
            logger.warning(f'Block {block.height} đã tồn tại, bỏ qua')
            return None

        logger.info(f'Đang xử lý Block {block.height}...')

        all_addresses = set()
        transactions_data = block_data.get('tx', [])
        
        # Thu thập tất cả địa chỉ
        for tx_json in transactions_data:
            for inp in tx_json.get('inputs', []):
                if 'prev_out' in inp and 'addr' in inp['prev_out']:
                    all_addresses.add(inp['prev_out']['addr'])
            for out in tx_json.get('out', []):
                if 'addr' in out:
                    all_addresses.add(out['addr'])

        # 2. Bulk Create Addresses
        if all_addresses:
            existing_addresses = set(Address.objects.filter(address__in=all_addresses).values_list('address', flat=True))
            new_addresses = [Address(address=addr) for addr in all_addresses if addr not in existing_addresses]
            if new_addresses:
                Address.objects.bulk_create(new_addresses, ignore_conflicts=True)
                logger.info(f'Tạo {len(new_addresses)} địa chỉ mới')

        # Load addresses vào memory
        address_map = {addr.address: addr for addr in Address.objects.filter(address__in=all_addresses)}

        # 3. Xử lý Transactions
        tx_to_create = []
        inputs_to_create = []
        outputs_to_create = []

        for tx_json in transactions_data:
            tx_hash = tx_json['hash']
            tx_time = datetime.fromtimestamp(tx_json.get('time', block.time.timestamp()), tz=dt_timezone.utc)
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
                    prev_tx_hash = prev_out.get('tx_index')
                    prev_output_index = prev_out.get('n')
                    prev_value = prev_out.get('value')
                    addr_str = prev_out.get('addr')
                    if addr_str:
                        addr_obj = address_map.get(addr_str)
                
                inputs_to_create.append(TxInput(
                    transaction=tx_obj,
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
                    transaction=tx_obj,
                    output_index=o,
                    value=out_json['value'],
                    address=addr_obj,
                    script_pub_key=out_json.get('script', ''),
                    is_spent=out_json.get('spent', False),
                ))

        # 4. Bulk Create
        if tx_to_create:
            Transaction.objects.bulk_create(tx_to_create, batch_size=500)
            logger.info(f'Tạo {len(tx_to_create)} giao dịch')

        # Load transactions vào memory để gán FK
        tx_map = {tx.hash: tx for tx in Transaction.objects.filter(block=block)}
        
        # Cập nhật FK cho Inputs và Outputs
        for inp in inputs_to_create:
            inp.transaction = tx_map[inp.transaction.hash]
            
        for out in outputs_to_create:
            out.transaction = tx_map[out.transaction.hash]

        # 5. Bulk Create Inputs & Outputs
        if inputs_to_create:
            TxInput.objects.bulk_create(inputs_to_create, batch_size=1000)
        if outputs_to_create:
            TxOutput.objects.bulk_create(outputs_to_create, batch_size=1000)
        
        logger.info(f'Tạo {len(inputs_to_create)} inputs và {len(outputs_to_create)} outputs')
        logger.info(f'Hoàn thành import Block {block.height}')
        
        return block.hash

    except IntegrityError as e:
        logger.error(f'Lỗi ràng buộc cơ sở dữ liệu: {str(e)}')
        raise Exception(f'Lỗi ràng buộc cơ sở dữ liệu: {str(e)}')
    except Exception as e:
        logger.error(f'Lỗi không mong muốn khi xử lý block: {str(e)}')
        raise Exception(f'Lỗi khi xử lý dữ liệu block: {str(e)}')
