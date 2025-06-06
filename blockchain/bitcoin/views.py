# blockchain/views.py
from django.shortcuts import render
from django.http import JsonResponse
from .models import Address, Transaction, TxInput, TxOutput, AddressCluster
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
import logging
from collections import defaultdict
from datetime import timezone
from django.db import models

logger = logging.getLogger(__name__)

def get_transaction_color(anomaly_score):
    """Tính màu giao dịch dựa trên anomaly_score (0: xanh lá -> 10: đỏ)."""
    score = min(max(anomaly_score, 0), 10)  # Giới hạn score trong [0, 10]
    green = int(255 * (1 - score / 10))  # Giảm xanh từ 255 -> 0
    red = int(255 * (score / 10))  # Tăng đỏ từ 0 -> 255
    return f"#{red:02x}{green:02x}00"  # Màu hex (RGB)

def get_address_color(tags):
    """Tính màu địa chỉ dựa trên tags, ưu tiên clustered."""
    if not tags:
        return "#00BFFF"  # Màu xanh dương mặc định
    tags_set = set(tags.split(',')) if tags else set()
    if 'clustered' in tags_set:
        return "#800080"  # Tím cho clustered
    if 'high_reuse' in tags_set:
        return "#FF0000"  # Đỏ cho high_reuse
    if 'reuse' in tags_set:
        return "#FFA500"  # Cam cho reuse
    return "#00BFFF"  # Mặc định

# --- VIEW CHO TRANG ĐỊA CHỈ ---
def graph_view(request):
    """Render trang HTML chính chứa đồ thị (bắt đầu từ địa chỉ)."""
    return render(request, 'bitcoin/graph.html')

# --- VIEW CHO TRANG GIAO DỊCH ---
def tx_graph_view(request):
    """Render trang HTML để xem đồ thị bắt đầu từ một TxID."""
    return render(request, 'bitcoin/tx_graph.html')

# --- VIEW CHO TRANG CLUSTER ---
def cluster_graph_view(request):
    """Render trang HTML để xem đồ thị của một cụm."""
    return render(request, 'bitcoin/cluster_graph.html')

# --- VIEW CHO TRANG DANH SÁCH GIAO DỊCH ---
def list_tx_view(request):
    """Render trang HTML hiển thị danh sách giao dịch bất thường."""
    return render(request, 'bitcoin/list_tx.html')

# --- API LẤY DỮ LIỆU THEO ĐỊA CHỈ ---
def get_address_transactions_data(request, address_hash):
    """Lấy dữ liệu giao dịch cho một địa chỉ và trả về dưới dạng JSON."""
    limit = 50

    try:
        address_obj = Address.objects.get(address=address_hash)
        
        inputs_query = TxInput.objects.filter(address=address_obj).select_related('transaction__block')
        outputs_query = TxOutput.objects.filter(address=address_obj).select_related('transaction__block')

        input_tx_hashes = list(inputs_query.values_list('transaction__hash', flat=True))
        output_tx_hashes = list(outputs_query.values_list('transaction__hash', flat=True))
        
        related_tx_hashes = list(set(input_tx_hashes + output_tx_hashes))[:limit]

        if not related_tx_hashes:
            return JsonResponse({'nodes': [], 'edges': [], 'transactions': []})

        transactions = Transaction.objects.filter(
            hash__in=related_tx_hashes
        ).prefetch_related(
            'inputs__address', 
            'outputs__address'
        ).order_by('-time')

        nodes = []
        edges = []
        transactions_list = []
        node_ids = set()

        def add_node(node_id, label, group, color, title):
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    'id': node_id,
                    'label': label,
                    'group': group,
                    'color': color,
                    'title': title
                })

        for tx in transactions:
            tx_hash = tx.hash
            tx_label = f"{tx_hash[:6]}..."
            tx_title = f"Giao dịch: {tx_hash}\nThời gian: {tx.time}\nPhí: {tx.fee} sats\nTags: {tx.tags or 'None'}"
            color = get_transaction_color(tx.anomaly_score)
            add_node(tx_hash, tx_label, 'transaction', color, tx_title)

            inputs_summary = defaultdict(int)
            outputs_summary = defaultdict(int)
            tx_inputs_info = []
            tx_outputs_info = []

            for inp in tx.inputs.all():
                if inp.address:
                    addr = inp.address.address
                    value = inp.prev_value or 0
                    inputs_summary[addr] += value
                    tx_inputs_info.append({
                        'address': addr,
                        'value': value,
                        'tags': inp.address.tags or 'None'
                    })

            for out in tx.outputs.all():
                if out.address:
                    addr = out.address.address
                    value = out.value or 0
                    outputs_summary[addr] += value
                    tx_outputs_info.append({
                        'address': addr,
                        'value': value,
                        'tags': out.address.tags or 'None'
                    })

            for addr, total_value in inputs_summary.items():
                addr_obj = Address.objects.get(address=addr)
                color = get_address_color(addr_obj.tags)
                add_node(addr, f"{addr[:8]}...", 'address', color, f"Địa chỉ: {addr}\nTags: {addr_obj.tags or 'None'}")
                edges.append({
                    'from': addr,
                    'to': tx_hash,
                    'label': f"{total_value / 100000000:.4f} BTC",
                    'arrows': 'to',
                    'title': f"Tổng vào: {total_value} sats từ {addr}"
                })

            for addr, total_value in outputs_summary.items():
                addr_obj = Address.objects.get(address=addr)
                color = get_address_color(addr_obj.tags)
                add_node(addr, f"{addr[:8]}...", 'address', color, f"Địa chỉ: {addr}\nTags: {addr_obj.tags or 'None'}")
                edges.append({
                    'from': tx_hash,
                    'to': addr,
                    'label': f"{total_value / 100000000:.4f} BTC",
                    'arrows': 'to',
                    'title': f"Tổng ra: {total_value} sats đến {addr}"
                })

            transactions_list.append({
                'tx_hash': tx_hash,
                'time': tx.time.strftime('%Y-%m-%d %H:%M'),
                'fee': tx.fee,
                'total_input': sum(inputs_summary.values()),
                'total_output': sum(outputs_summary.values()),
                'inputs': tx_inputs_info,
                'outputs': tx_outputs_info,
                'tags': tx.tags or 'None',
                'anomaly_score': tx.anomaly_score
            })

        return JsonResponse({
            'nodes': nodes,
            'edges': edges,
            'transactions': transactions_list,
            'queried_node': address_hash
        })

    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy địa chỉ trong cơ sở dữ liệu'}, status=404)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu cho địa chỉ {address_hash}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

# --- API LẤY DỮ LIỆU THEO TXID ---
def get_transaction_graph_data(request, tx_hash):
    """Lấy dữ liệu đồ thị cho một TxID cụ thể."""
    try:
        tx = Transaction.objects.prefetch_related(
            'inputs__address',
            'outputs__address'
        ).get(hash=tx_hash)

        nodes = []
        edges = []
        node_ids = set()

        def add_node(node_id, label, group, color, title):
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    'id': node_id,
                    'label': label,
                    'group': group,
                    'color': color,
                    'title': title
                })

        tx_label = f"{tx.hash[:8]}..."
        tx_title = f"Giao dịch: {tx.hash}\nThời gian: {tx.time}\nPhí: {tx.fee} sats\nTags: {tx.tags or 'None'}"
        color = get_transaction_color(tx.anomaly_score)
        add_node(tx.hash, tx_label, 'center_transaction', color, tx_title)

        inputs_summary = defaultdict(int)
        tx_inputs_info = []
        for inp in tx.inputs.all():
            if inp.address:
                addr = inp.address.address
                value = inp.prev_value or 0
                inputs_summary[addr] += value
                tx_inputs_info.append({
                    'address': addr,
                    'value': value,
                    'tags': inp.address.tags or 'None'
                })

        for addr, total_value in inputs_summary.items():
            addr_obj = Address.objects.get(address=addr)
            color = get_address_color(addr_obj.tags)
            add_node(addr, f"{addr[:8]}...", 'address', color, f"Địa chỉ: {addr}\nTags: {addr_obj.tags or 'None'}")
            edges.append({
                'from': addr,
                'to': tx.hash,
                'label': f"{total_value / 100000000:.4f} BTC",
                'arrows': 'to',
                'title': f"Tổng vào: {total_value} sats từ {addr}"
            })

        outputs_summary = defaultdict(int)
        tx_outputs_info = []
        for out in tx.outputs.all():
            if out.address:
                addr = out.address.address
                value = out.value or 0
                outputs_summary[addr] += value
                tx_outputs_info.append({
                    'address': addr,
                    'value': value,
                    'tags': out.address.tags or 'None'
                })

        for addr, total_value in outputs_summary.items():
            addr_obj = Address.objects.get(address=addr)
            color = get_address_color(addr_obj.tags)
            add_node(addr, f"{addr[:8]}...", 'address', color, f"Địa chỉ: {addr}\nTags: {addr_obj.tags or 'None'}")
            edges.append({
                'from': tx.hash,
                'to': addr,
                'label': f"{total_value / 100000000:.4f} BTC",
                'arrows': 'to',
                'title': f"Tổng ra: {total_value} sats đến {addr}"
            })

        transactions_list = [{
            'tx_hash': tx.hash,
            'time': tx.time.strftime('%Y-%m-%d %H:%M'),
            'fee': tx.fee,
            'total_input': sum(inputs_summary.values()),
            'total_output': sum(outputs_summary.values()),
            'inputs': tx_inputs_info,
            'outputs': tx_outputs_info,
            'tags': tx.tags or 'None',
            'anomaly_score': tx.anomaly_score
        }]

        return JsonResponse({
            'nodes': nodes,
            'edges': edges,
            'transactions': transactions_list,
            'center_node': tx.hash
        })

    except Transaction.DoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy giao dịch'}, status=404)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu cho giao dịch {tx_hash}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

# --- API LẤY DỮ LIỆU THEO CLUSTER ID ---
def get_cluster_graph_data(request, cluster_id):
    """Lấy dữ liệu đồ thị cho một cluster cụ thể."""
    limit = 100  # Giới hạn tổng số giao dịch trả về

    try:
        # Lấy thông tin về cluster
        cluster = AddressCluster.objects.get(cluster_id=cluster_id)
        addresses = Address.objects.filter(cluster=cluster)
        address_count = addresses.count()
        
        if address_count == 0:
            return JsonResponse({
                'error': f'Không tìm thấy địa chỉ nào trong cluster {cluster_id}',
            }, status=404)

        # Lấy tối đa 20 địa chỉ đầu tiên để hiển thị
        address_sample = list(addresses.values_list('address', flat=True)[:20])
            
        # Lấy các giao dịch liên quan đến các địa chỉ trong cluster
        address_ids = list(addresses.values_list('address', flat=True))
        
        # Tìm các input và output có liên quan
        inputs = TxInput.objects.filter(address__address__in=address_ids).select_related('transaction', 'address')
        outputs = TxOutput.objects.filter(address__address__in=address_ids).select_related('transaction', 'address')
        
        # Lấy các hash giao dịch duy nhất từ inputs và outputs
        input_tx_hashes = set(inputs.values_list('transaction__hash', flat=True))
        output_tx_hashes = set(outputs.values_list('transaction__hash', flat=True))
        
        # Kết hợp và giới hạn số lượng giao dịch
        related_tx_hashes = list(input_tx_hashes.union(output_tx_hashes))[:limit]
        
        if not related_tx_hashes:
            return JsonResponse({
                'nodes': [], 
                'edges': [], 
                'transactions': [],
                'cluster_info': {
                    'cluster_id': cluster_id,
                    'address_count': address_count,
                    'notes': cluster.notes,
                    'addresses': address_sample
                }
            })

        # Lấy chi tiết các giao dịch
        transactions = Transaction.objects.filter(
            hash__in=related_tx_hashes
        ).prefetch_related(
            'inputs__address', 
            'outputs__address'
        ).order_by('-time')

        # Chuẩn bị dữ liệu để trả về
        nodes = []
        edges = []
        transactions_list = []
        node_ids = set()

        def add_node(node_id, label, group, color, title, in_cluster=False):
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    'id': node_id,
                    'label': label,
                    'group': group,
                    'color': color,
                    'title': title,
                    'in_cluster': in_cluster
                })

        # Thêm nút trung tâm cho cluster
        cluster_label = f"Cluster {cluster_id[:6]}..."
        cluster_title = f"Cluster: {cluster_id}\nSố địa chỉ: {address_count}\nGhi chú: {cluster.notes or 'Không có'}"
        add_node(cluster_id, cluster_label, 'cluster', '#8A2BE2', cluster_title)  # Tím đậm cho cluster

        for tx in transactions:
            tx_hash = tx.hash
            tx_label = f"{tx_hash[:6]}..."
            tx_title = f"Giao dịch: {tx_hash}\nThời gian: {tx.time}\nPhí: {tx.fee} sats\nTags: {tx.tags or 'None'}"
            color = get_transaction_color(tx.anomaly_score)
            add_node(tx_hash, tx_label, 'transaction', color, tx_title)

            inputs_summary = defaultdict(int)
            outputs_summary = defaultdict(int)
            tx_inputs_info = []
            tx_outputs_info = []

            for inp in tx.inputs.all():
                if inp.address:
                    addr = inp.address.address
                    value = inp.prev_value or 0
                    inputs_summary[addr] += value
                    tx_inputs_info.append({
                        'address': addr,
                        'value': value,
                        'tags': inp.address.tags or 'None'
                    })

            for out in tx.outputs.all():
                if out.address:
                    addr = out.address.address
                    value = out.value or 0
                    outputs_summary[addr] += value
                    tx_outputs_info.append({
                        'address': addr,
                        'value': value,
                        'tags': out.address.tags or 'None'
                    })

            for addr, total_value in inputs_summary.items():
                addr_obj = Address.objects.get(address=addr)
                color = get_address_color(addr_obj.tags)
                in_cluster = addr in address_ids
                add_node(addr, f"{addr[:8]}...", 'address', color, f"Địa chỉ: {addr}\nTags: {addr_obj.tags or 'None'}\nTrong cluster: {'Có' if in_cluster else 'Không'}", in_cluster)
                edges.append({
                    'from': addr,
                    'to': tx_hash,
                    'label': f"{total_value / 100000000:.4f} BTC",
                    'arrows': 'to',
                    'title': f"Tổng vào: {total_value} sats từ {addr}"
                })

            for addr, total_value in outputs_summary.items():
                addr_obj = Address.objects.get(address=addr)
                color = get_address_color(addr_obj.tags)
                in_cluster = addr in address_ids
                add_node(addr, f"{addr[:8]}...", 'address', color, f"Địa chỉ: {addr}\nTags: {addr_obj.tags or 'None'}\nTrong cluster: {'Có' if in_cluster else 'Không'}", in_cluster)
                edges.append({
                    'from': tx_hash,
                    'to': addr,
                    'label': f"{total_value / 100000000:.4f} BTC",
                    'arrows': 'to',
                    'title': f"Tổng ra: {total_value} sats đến {addr}"
                })

            transactions_list.append({
                'tx_hash': tx_hash,
                'time': tx.time.strftime('%Y-%m-%d %H:%M'),
                'fee': tx.fee,
                'total_input': sum(inputs_summary.values()),
                'total_output': sum(outputs_summary.values()),
                'inputs': tx_inputs_info,
                'outputs': tx_outputs_info,
                'tags': tx.tags or 'None',
                'anomaly_score': tx.anomaly_score
            })

        # Thêm các kết nối từ cluster đến các địa chỉ trong cluster
        for addr in node_ids:
            if addr in address_ids and addr != cluster_id:edges.append({
                    'from': cluster_id,
                    'to': addr,
                    'dashes': True,  # Đường đứt nét
                    'width': 1,
                    'color': { 'color': '#8A2BE2', 'opacity': 0.6 },
                    'arrows': '',
                    'title': 'Thuộc cluster này',
                    'label': 'Thuộc cluster'  # Thêm thuộc tính label để tránh lỗi JS
                })

        return JsonResponse({
            'nodes': nodes,
            'edges': edges,
            'transactions': transactions_list,
            'cluster_info': {
                'cluster_id': cluster_id,
                'address_count': address_count,
                'notes': cluster.notes,
                'addresses': address_sample
            }
        })

    except AddressCluster.DoesNotExist:
        return JsonResponse({'error': f'Không tìm thấy cluster {cluster_id}'}, status=404)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu cho cluster {cluster_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

# --- API LẤY DANH SÁCH GIAO DỊCH BẤT THƯỜNG ---
def get_transactions_list(request):
    """API endpoint để lấy danh sách giao dịch bất thường theo bộ lọc."""
    try:
        logger.info(f"Request params: {request.GET}")
        # Lấy các tham số từ request
        limit = int(request.GET.get('limit', 100))
        block = request.GET.get('block')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        logger.info(f"Processed params: limit={limit}, block={block}, start_date={start_date}, end_date={end_date}")
        
        # Giới hạn số lượng kết quả trả về
        if limit > 1000:
            limit = 1000
        
        # Bắt đầu với tất cả các giao dịch
        query = Transaction.objects.all()        # Lọc theo khối (nếu có)
        if block:
            try:
                block_height = int(block)
                query = query.filter(block__height=block_height)
            except ValueError:
                return JsonResponse({'error': 'Giá trị khối không hợp lệ'}, status=400)
          # Lọc theo ngày bắt đầu (nếu có)
        if start_date:
            query = query.filter(time__gte=start_date)
        
        # Lọc theo ngày kết thúc (nếu có)
        if end_date:
            if isinstance(end_date, str) and len(end_date.strip()) > 0:
                query = query.filter(time__lte=end_date + ' 23:59:59')
            elif end_date:
                query = query.filter(time__lte=end_date)
        
        # Lấy các giao dịch có điểm bất thường cao nhất
        transactions = query.order_by('-anomaly_score')[:limit]
        
        # Chuẩn bị dữ liệu trả về
        transactions_list = []
        
        for tx in transactions:
            # Lấy danh sách inputs của giao dịch
            inputs = TxInput.objects.filter(transaction=tx).select_related('address')
            tx_inputs_info = []
            for inp in inputs:
                tx_inputs_info.append({
                    'address': inp.address.address if inp.address else 'Unknown',
                    'value': inp.prev_value or 0,
                    'tags': inp.address.tags if inp.address else None
                })
            
            # Lấy danh sách outputs của giao dịch
            outputs = TxOutput.objects.filter(transaction=tx).select_related('address')
            tx_outputs_info = []
            
            for out in outputs:
                tx_outputs_info.append({
                    'address': out.address.address if out.address else 'Unknown',
                    'value': out.value,
                    'tags': out.address.tags if out.address else None
                })
            
            # Thêm thông tin giao dịch vào danh sách
            transactions_list.append({
                'tx_hash': tx.hash,
                'time': tx.time.strftime('%Y-%m-%d %H:%M') if tx.time else 'Unknown',
                'block_height': tx.block.height if tx.block else None,
                'fee': tx.fee,
                'total_input': sum(inp['value'] for inp in tx_inputs_info),
                'total_output': sum(out['value'] for out in tx_outputs_info),
                'inputs': tx_inputs_info,
                'outputs': tx_outputs_info,
                'tags': tx.tags or 'None',
                'anomaly_score': tx.anomaly_score
            })
        
        return JsonResponse({
            'transactions': transactions_list
        })
    
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách giao dịch: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)
    # --- API LẤY DANH SÁCH GIAO DỊCH CHO MODAL ---
def get_transactions_modal(request):
    """API endpoint để lấy danh sách giao dịch cho modal với phân trang."""
    try:
        # Lấy các tham số từ request
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        sort = request.GET.get('sort', 'time_desc')
        
        # Giới hạn số lượng kết quả trả về
        if limit > 100:
            limit = 100
        
        # Bắt đầu với tất cả các giao dịch
        query = Transaction.objects.all()
        
        # Áp dụng sắp xếp
        if sort == 'time_desc':
            query = query.order_by('-time')
        elif sort == 'time_asc':
            query = query.order_by('time')
        elif sort == 'anomaly_desc':
            query = query.order_by('-anomaly_score', '-time')
        elif sort == 'fee_desc':
            query = query.order_by('-fee', '-time')
        else:
            query = query.order_by('-time')  # Default
        
        # Đếm tổng số giao dịch
        total_count = query.count()
        
        # Áp dụng phân trang
        transactions = query[offset:offset + limit]
        
        # Chuẩn bị dữ liệu trả về
        transactions_list = []
        anomaly_count = 0
        
        for tx in transactions:
            if tx.anomaly_score >= 6:  # Điểm bất thường từ 6 trở lên
                anomaly_count += 1
                
            # Lấy tổng input và output
            total_input = TxInput.objects.filter(transaction=tx).aggregate(
                total=models.Sum('prev_value'))['total'] or 0
            total_output = TxOutput.objects.filter(transaction=tx).aggregate(
                total=models.Sum('value'))['total'] or 0
            
            transactions_list.append({
                'tx_hash': tx.hash,
                'time': tx.time.strftime('%Y-%m-%d %H:%M') if tx.time else 'Unknown',
                'block_height': tx.block.height if tx.block else None,
                'fee': tx.fee,
                'total_input': total_input,
                'total_output': total_output,
                'tags': tx.tags or 'None',
                'anomaly_score': tx.anomaly_score
            })
        
        # Tính toán thông tin phân trang
        total_pages = (total_count + limit - 1) // limit  # Ceiling division
        current_page = (offset // limit) + 1
        
        return JsonResponse({
            'transactions': transactions_list,
            'total': total_count,
            'page': current_page,
            'total_pages': total_pages,
            'limit': limit,
            'anomaly_count': anomaly_count
        })
    
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách giao dịch modal: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

def get_addresses_modal(request):
    """API endpoint để lấy danh sách địa chỉ cho modal với phân trang."""
    try:
        # Lấy các tham số từ request
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        sort = request.GET.get('sort', 'tx_count_desc')
        tag = request.GET.get('tag', '')
        min_tx = request.GET.get('min_tx', '')
        
        # Giới hạn số lượng kết quả trả về
        if limit > 100:
            limit = 100
        
        # Bắt đầu với tất cả các địa chỉ
        query = Address.objects.all()
        
        # Lọc theo tag nếu có
        if tag:
            query = query.filter(tags__icontains=tag)
        
        # Lọc theo số giao dịch tối thiểu nếu có
        if min_tx:
            try:
                min_tx_count = int(min_tx)
                query = query.filter(tx_count__gte=min_tx_count)
            except ValueError:
                pass
        
        # Áp dụng sắp xếp (bỏ balance_desc vì không có trường balance)
        if sort == 'tx_count_desc':
            query = query.order_by('-tx_count')
        elif sort == 'tx_count_asc':
            query = query.order_by('tx_count')
        elif sort == 'first_seen_desc':
            query = query.order_by('-first_seen')
        elif sort == 'last_seen_desc':
            query = query.order_by('-last_seen')
        else:
            query = query.order_by('-tx_count')  # Default
        
        # Đếm tổng số địa chỉ
        total_count = query.count()
        
        # Áp dụng phân trang
        addresses = query[offset:offset + limit]
        
        # Chuẩn bị dữ liệu trả về
        addresses_list = []
        clustered_count = 0
        high_reuse_count = 0
        
        for addr in addresses:
            if addr.tags:
                if 'clustered' in addr.tags.lower():
                    clustered_count += 1
                if 'high_reuse' in addr.tags.lower():
                    high_reuse_count += 1
            
            # Tính số dư từ UTXO chưa chi tiêu
            balance = TxOutput.objects.filter(
                address=addr, 
                is_spent=False
            ).aggregate(total=models.Sum('value'))['total'] or 0
            
            addresses_list.append({
                'address': addr.address,
                'balance': balance,
                'tx_count': addr.tx_count or 0,
                'first_seen': addr.first_seen.strftime('%Y-%m-%d') if addr.first_seen else None,
                'last_seen': addr.last_seen.strftime('%Y-%m-%d') if addr.last_seen else None,
                'tags': addr.tags or 'None'
            })
        
        # Tính toán thông tin phân trang
        total_pages = (total_count + limit - 1) // limit  # Ceiling division
        current_page = (offset // limit) + 1
        
        return JsonResponse({
            'addresses': addresses_list,
            'total': total_count,
            'page': current_page,
            'total_pages': total_pages,
            'limit': limit,
            'clustered_count': clustered_count,
            'high_reuse_count': high_reuse_count
        })
    
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách địa chỉ modal: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

def get_clusters_modal(request):
    """API endpoint để lấy danh sách clusters cho modal với phân trang."""
    try:
        # Lấy các tham số từ request
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        sort = request.GET.get('sort', 'address_count_desc')
        min_address = request.GET.get('min_address', '')
        max_address = request.GET.get('max_address', '')
        
        # Giới hạn số lượng kết quả trả về
        if limit > 100:
            limit = 100
        
        # Bắt đầu với tất cả các cluster
        query = AddressCluster.objects.all()
        
        # Lọc theo số địa chỉ tối thiểu nếu có
        if min_address:
            try:
                min_addr_count = int(min_address)
                query = query.filter(address_count__gte=min_addr_count)
            except ValueError:
                pass
        
        # Lọc theo số địa chỉ tối đa nếu có
        if max_address:
            try:
                max_addr_count = int(max_address)
                query = query.filter(address_count__lte=max_addr_count)
            except ValueError:
                pass
        
        # Áp dụng sắp xếp
        if sort == 'address_count_desc':
            query = query.order_by('-address_count')
        elif sort == 'address_count_asc':
            query = query.order_by('address_count')
        elif sort == 'created_desc':
            query = query.order_by('-created_at')
        elif sort == 'updated_desc':
            query = query.order_by('-updated_at')
        else:
            query = query.order_by('-address_count')  # Default
        
        # Đếm tổng số cluster
        total_count = query.count()
        
        # Áp dụng phân trang
        clusters = query[offset:offset + limit]
        
        # Chuẩn bị dữ liệu trả về
        clusters_list = []
        large_clusters_count = 0  # Cluster có > 50 địa chỉ
        with_notes_count = 0
        
        for cluster in clusters:
            if cluster.address_count >= 50:
                large_clusters_count += 1
            if cluster.notes and cluster.notes.strip():
                with_notes_count += 1
                
            clusters_list.append({
                'cluster_id': cluster.cluster_id,
                'address_count': cluster.address_count,
                'created_at': cluster.created_at.strftime('%Y-%m-%d') if cluster.created_at else None,
                'updated_at': cluster.updated_at.strftime('%Y-%m-%d') if cluster.updated_at else None,
                'notes': cluster.notes or None
            })
        
        # Tính toán thông tin phân trang
        total_pages = (total_count + limit - 1) // limit  # Ceiling division
        current_page = (offset // limit) + 1
        
        # Đếm cluster lớn và có ghi chú trong toàn bộ dataset (không chỉ trang hiện tại)
        total_large_clusters = AddressCluster.objects.filter(address_count__gte=50).count()
        total_with_notes = AddressCluster.objects.exclude(notes__isnull=True).exclude(notes__exact='').count()
        
        return JsonResponse({
            'clusters': clusters_list,
            'total': total_count,
            'page': current_page,
            'total_pages': total_pages,
            'limit': limit,
            'large_clusters_count': total_large_clusters,
            'with_notes_count': total_with_notes
        })
    
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách cluster modal: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)
