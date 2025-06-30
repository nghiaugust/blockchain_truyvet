from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.core.management import call_command
from django.db import transaction, IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from bitcoin.models import Block, Transaction, Address, TxInput, TxOutput, AddressCluster
import requests
import json
import logging
from datetime import datetime, timezone as dt_timezone
from io import StringIO
import sys
import uuid

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

        # Bước 4: Chạy phân cụm địa chỉ (address clustering)
        try:
            logger.info(f'Bắt đầu chạy address clustering cho block {block_height}')
            
            # Capture output from clustering command
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = captured_output = StringIO()
            sys.stderr = captured_error = StringIO()
            
            call_command('groups', '--chunk-size=1000', f'--start-block={block_height}')
            
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            clustering_output = captured_output.getvalue()
            clustering_error = captured_error.getvalue()
            
            if clustering_error:
                logger.warning(f'Clustering stderr: {clustering_error}')
            
            logger.info(f'Hoàn thành phân cụm địa chỉ cho block {block_height}')
            logger.info(f'Clustering output: {clustering_output[:500]}...' if len(clustering_output) > 500 else f'Clustering output: {clustering_output}')
            
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            logger.error(f'Lỗi khi chạy address clustering: {str(e)}')
            # Không return error, chỉ warning vì import đã thành công
            logger.warning(f'Import block {block_height} thành công nhưng clustering bị lỗi: {str(e)}')
        
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
            'message': f'Import thành công khối {block_height} và hoàn thành phân tích (heuristics + clustering)',
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
        
        # Thực hiện clustering ngay sau khi import xong
        try:
            logger.info(f'Bắt đầu clustering cho block {block.height}')
            clustering_result = cluster_addresses_for_block(block.height)
            if clustering_result:
                logger.info(f'Clustering thành công: {clustering_result}')
            else:
                logger.warning(f'Clustering không thành công cho block {block.height}')
        except Exception as e:
            logger.error(f'Lỗi khi clustering block {block.height}: {str(e)}')
            # Không raise error, chỉ log warning vì import đã thành công
        
        return block.hash

    except IntegrityError as e:
        logger.error(f'Lỗi ràng buộc cơ sở dữ liệu: {str(e)}')
        raise Exception(f'Lỗi ràng buộc cơ sở dữ liệu: {str(e)}')
    except Exception as e:
        logger.error(f'Lỗi không mong muốn khi xử lý block: {str(e)}')
        raise Exception(f'Lỗi khi xử lý dữ liệu block: {str(e)}')

# ============ ADDRESS CLUSTERING FUNCTIONS ============

class UnionFind:
    """
    Union-Find data structure để phân cụm địa chỉ Bitcoin
    """
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


def cluster_addresses_for_block(block_height):
    """
    Thực hiện phân cụm địa chỉ cho một block cụ thể
    """
    try:
        logger.info(f'Bắt đầu clustering cho block {block_height}')
        
        # Lấy tất cả giao dịch trong block
        block = Block.objects.get(height=block_height)
        transactions = Transaction.objects.filter(block=block).prefetch_related('inputs', 'inputs__address')
        
        uf = UnionFind()
        
        # Khởi tạo tất cả địa chỉ trong block
        for tx in transactions:
            input_addresses = {inp.address.address for inp in tx.inputs.all() if inp.address}
            for addr in input_addresses:
                uf.make_set(addr)
        
        # Hợp nhất các địa chỉ đầu vào trong cùng giao dịch
        clustered_tx_count = 0
        for tx in transactions:
            input_addresses = [inp.address.address for inp in tx.inputs.all() if inp.address]
            if len(input_addresses) > 1:  # Chỉ xử lý giao dịch có nhiều địa chỉ đầu vào
                first_addr = input_addresses[0]
                for addr in input_addresses[1:]:
                    uf.union(first_addr, addr)
                clustered_tx_count += 1
        
        # Tạo danh sách cụm
        clusters = {}
        for addr in uf.parent:
            root = uf.find(addr)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(addr)
        
        # Lưu cụm vào database
        cluster_count, address_count = save_clusters_to_db(clusters)
        
        logger.info(f'Block {block_height}: Phân tích {len(transactions)} giao dịch, '
                   f'tìm thấy {clustered_tx_count} giao dịch có nhiều input, '
                   f'tạo/cập nhật {cluster_count} cụm cho {address_count} địa chỉ')
        
        return {
            'transactions_analyzed': len(transactions),
            'multi_input_transactions': clustered_tx_count,
            'clusters_created': cluster_count,
            'addresses_clustered': address_count
        }
        
    except Block.DoesNotExist:
        logger.error(f'Block {block_height} không tồn tại')
        return None
    except Exception as e:
        logger.error(f'Lỗi khi clustering block {block_height}: {str(e)}')
        return None


def save_clusters_to_db(clusters):
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


@csrf_exempt
def cluster_addresses_api(request):
    """
    API endpoint để chạy clustering cho một block cụ thể
    """
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
        
        # Thực hiện clustering
        result = cluster_addresses_for_block(block_height)
        
        if result:
            return JsonResponse({
                'success': True,
                'message': f'Clustering thành công cho block {block_height}',
                'data': result
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Không thể clustering block {block_height}'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Dữ liệu JSON không hợp lệ'})
    except Exception as e:
        logger.error(f'Lỗi không mong muốn trong clustering API: {str(e)}')
        return JsonResponse({'success': False, 'message': f'Lỗi không mong muốn: {str(e)}'})
