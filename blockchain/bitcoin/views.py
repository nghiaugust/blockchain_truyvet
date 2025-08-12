# blockchain/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum, Q
import json
import re
from django.http import HttpResponseRedirect

# Import từ file advanced_coinjoin.py
from .management.commands.advanced_coinjoin import AdvancedCoinJoinDetector, AddressTree
from .models import Transaction, TxInput, TxOutput, Address, AddressCluster
from django.core.exceptions import ObjectDoesNotExist
import logging
from collections import defaultdict
from datetime import timezone
from django.db import models

# Import cho recursive CoinJoin detector
from .management.commands.recursive_coinjoin_detector import RecursiveCoinJoinDetector

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
        return "#666666"  # Xám cho địa chỉ không có tag
    
    tags_set = set(tags.split(','))
    
    # Ưu tiên clustered
    if 'clustered' in tags_set:
        return "#800080"  # Tím cho clustered
    elif 'coinjoin' in tags_set:
        return "#FF6B6B"  # Đỏ cho coinjoin
    elif 'high_reuse' in tags_set:
        return "#4ECDC4"  # Xanh lá cho high reuse
    elif 'reuse' in tags_set:
        return "#45B7D1"  # Xanh dương cho reuse
    elif 'new' in tags_set:
        return "#96CEB4"  # Xanh nhạt cho new
    else:
        return "#FFA07A"  # Cam cho các tag khác

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
    """View cho trang cluster graph."""
    return render(request, 'bitcoin/cluster_graph.html')



def calculate_address_balance(bitcoin_address):
    """Hàm tính số dư của một địa chỉ Bitcoin"""
    try:
        # Tìm address trong bitcoin app
        address_obj = Address.objects.filter(address=bitcoin_address).first()
        if not address_obj:
            return 0  # Không tìm thấy địa chỉ trong database
        
        # Tính tổng UTXO (outputs chưa spend)
        unspent_outputs = TxOutput.objects.filter(
            address=address_obj,
            is_spent=False  # Chỉ lấy outputs chưa được spend
        ).aggregate(total=Sum('value'))['total'] or 0
        
        # Chuyển từ satoshi sang BTC
        balance_btc = unspent_outputs / 100000000
        return balance_btc
        
    except Exception as e:
        print(f"Lỗi khi tính số dư cho {bitcoin_address}: {e}")
        return 0

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
        # Lấy cluster
        cluster = AddressCluster.objects.get(cluster_id=cluster_id)
        
        # Lấy các địa chỉ trong cluster
        addresses = cluster.addresses.all()
        
        # Khởi tạo dữ liệu đồ thị
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
        
        # Thêm các địa chỉ vào đồ thị
        for addr in addresses:
            color = get_address_color(addr.tags)
            add_node(addr.address, f"{addr.address[:8]}...", 'address', color, 
                    f"Địa chỉ: {addr.address}\nTags: {addr.tags or 'None'}")
        
        # Lấy các giao dịch liên quan đến cluster này
        transactions = Transaction.objects.filter(
            inputs__address__in=addresses
        ).distinct()[:limit]
        
        # Thêm các giao dịch vào đồ thị
        for tx in transactions:
            tx_label = f"{tx.hash[:8]}..."
            tx_title = f"Giao dịch: {tx.hash}\nThời gian: {tx.time}\nPhí: {tx.fee} sats\nTags: {tx.tags or 'None'}"
            color = get_transaction_color(tx.anomaly_score)
            add_node(tx.hash, tx_label, 'transaction', color, tx_title)
            
            # Thêm các cạnh từ địa chỉ đến giao dịch
            for inp in tx.inputs.all():
                if inp.address and inp.address in addresses:
                    edges.append({
                        'from': inp.address.address,
                        'to': tx.hash,
                        'arrows': 'to',
                        'title': f"Input từ {inp.address.address}"
                    })
            
            # Thêm các cạnh từ giao dịch đến địa chỉ
            for out in tx.outputs.all():
                if out.address and out.address in addresses:
                    edges.append({
                        'from': tx.hash,
                        'to': out.address.address,
                        'arrows': 'to',
                        'title': f"Output đến {out.address.address}"
                    })
        
        return JsonResponse({
            'nodes': nodes,
            'edges': edges,
            'cluster_id': cluster_id,
            'cluster_name': cluster.notes or f"Cluster {cluster_id}"
        })
        
    except AddressCluster.DoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy cluster'}, status=404)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu cho cluster {cluster_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)



# --- TRANSACTION LIST VIEWS ---
def get_transactions_list(request):
    """API để lấy danh sách giao dịch."""
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        offset = (page - 1) * limit
        
        transactions = Transaction.objects.all().order_by('-time')[offset:offset + limit]
        
        tx_list = []
        for tx in transactions:
            tx_list.append({
                'hash': tx.hash,
                'time': tx.time.strftime('%Y-%m-%d %H:%M'),
                'fee': tx.fee,
                'tags': tx.tags or 'None',
                'anomaly_score': tx.anomaly_score
            })
        
        return JsonResponse({
            'transactions': tx_list,
            'page': page,
            'limit': limit,
            'total_count': Transaction.objects.count()
        })
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách giao dịch: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

def get_transactions_modal(request):
    """API để lấy dữ liệu cho modal giao dịch."""
    try:
        tx_hash = request.GET.get('tx_hash')
        if not tx_hash:
            return JsonResponse({'error': 'Thiếu tx_hash'}, status=400)
        
        tx = Transaction.objects.get(hash=tx_hash)
        
        # Lấy thông tin inputs và outputs
        inputs = []
        for inp in tx.inputs.all():
            if inp.address:
                inputs.append({
                    'address': inp.address.address,
                    'value': inp.prev_value or 0,
                    'tags': inp.address.tags or 'None'
                })
        
        outputs = []
        for out in tx.outputs.all():
            if out.address:
                outputs.append({
                    'address': out.address.address,
                    'value': out.value or 0,
                    'tags': out.address.tags or 'None'
                })
        
        return JsonResponse({
            'hash': tx.hash,
            'time': tx.time.strftime('%Y-%m-%d %H:%M'),
            'fee': tx.fee,
            'tags': tx.tags or 'None',
            'anomaly_score': tx.anomaly_score,
            'inputs': inputs,
            'outputs': outputs
        })
    except Transaction.DoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy giao dịch'}, status=404)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu modal giao dịch: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

def get_addresses_modal(request):
    """API để lấy dữ liệu cho modal địa chỉ."""
    try:
        address = request.GET.get('address')
        if not address:
            return JsonResponse({'error': 'Thiếu address'}, status=400)
        
        addr_obj = Address.objects.get(address=address)
        
        # Lấy các giao dịch liên quan
        transactions = Transaction.objects.filter(
            inputs__address=addr_obj
        ).distinct()[:10]
        
        tx_list = []
        for tx in transactions:
            tx_list.append({
                'hash': tx.hash,
                'time': tx.time.strftime('%Y-%m-%d %H:%M'),
                'fee': tx.fee
            })
        
        return JsonResponse({
            'address': address,
            'balance': addr_obj.balance,
            'tags': addr_obj.tags or 'None',
            'transactions': tx_list
        })
    except Address.DoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy địa chỉ'}, status=404)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu modal địa chỉ: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

def get_clusters_modal(request):
    """API để lấy dữ liệu cho modal cluster."""
    try:
        cluster_id = request.GET.get('cluster_id')
        if not cluster_id:
            return JsonResponse({'error': 'Thiếu cluster_id'}, status=400)
        
        cluster = AddressCluster.objects.get(cluster_id=cluster_id)
        addresses = cluster.addresses.all()
        
        addr_list = []
        for addr in addresses:
            # Tính số dư
            balance = calculate_address_balance(addr.address)
            addr_list.append({
                'address': addr.address,
                'balance': balance,
                'tags': addr.tags or 'None'
            })
        
        return JsonResponse({
            'cluster_id': cluster_id,
            'name': cluster.notes or f"Cluster {cluster_id}",
            'addresses': addr_list,
            'total_addresses': addresses.count()
        })
    except AddressCluster.DoesNotExist:
        return JsonResponse({'error': 'Không tìm thấy cluster'}, status=404)
    except Exception as e:
        logger.error(f"Lỗi khi lấy dữ liệu modal cluster: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

def get_coinjoin_addresses_list(request):
    """API để lấy danh sách địa chỉ CoinJoin với phân trang."""
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        offset = (page - 1) * limit
        
        # Lấy địa chỉ có tag coinjoin
        coinjoin_addresses = Address.objects.filter(
            tags__icontains='coinjoin'
        ).prefetch_related('spent_txos__transaction', 'received_txos__transaction')
        
        # Tính tổng số
        total_count = coinjoin_addresses.count()
        
        # Phân trang
        addresses = coinjoin_addresses[offset:offset + limit]
        
        # Thu thập thông tin chi tiết
        address_list = []
        for addr in addresses:
            # Tính số dư
            balance = calculate_address_balance(addr.address)
            
            # Lấy các giao dịch liên quan
            input_txs = set()
            output_txs = set()
            
            # Lấy giao dịch input
            for inp in addr.spent_txos.all():
                if inp.transaction:
                    input_txs.add(inp.transaction.hash)
            
            # Lấy giao dịch output
            for out in addr.received_txos.all():
                if out.transaction:
                    output_txs.add(out.transaction.hash)
            
            address_list.append({
                'address': addr.address,
                'balance': balance,
                'tx_count': addr.tx_count,
                'tags': addr.tags or 'None',
                'color': get_address_color(addr.tags),
                'input_txs_count': len(input_txs),
                'output_txs_count': len(output_txs),
                'total_txs': len(input_txs) + len(output_txs),
                'first_seen': addr.first_seen.strftime('%Y-%m-%d %H:%M') if addr.first_seen else None,
                'last_seen': addr.last_seen.strftime('%Y-%m-%d %H:%M') if addr.last_seen else None
            })
        
        # Sắp xếp theo số lượng giao dịch (giảm dần)
        address_list.sort(key=lambda x: x['total_txs'], reverse=True)
        
        return JsonResponse({
            'addresses': address_list,
            'page': page,
            'limit': limit,
            'total_count': total_count,
            'total_pages': (total_count + limit - 1) // limit
        })
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách địa chỉ CoinJoin: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

# --- COINJOIN ADDRESS GROUPS VIEWS ---
def coinjoin_address_groups_view(request):
    """View cho màn hình hiển thị các nhóm địa chỉ CoinJoin."""
    return render(request, 'bitcoin/coinjoin_address_groups.html')

def get_coinjoin_address_groups(request):
    """API để lấy danh sách các nhóm địa chỉ CoinJoin."""
    try:
        # Lấy các giao dịch có thể là CoinJoin (nhiều I/O hoặc anomaly_score cao)
        coinjoin_transactions = Transaction.objects.filter(
            Q(tags__icontains='coinjoin') |
            Q(vin_sz__gte=5, vout_sz__gte=5) |  # Nhiều input/output
            Q(anomaly_score__gte=5.0)  # Anomaly score cao
        ).prefetch_related('inputs__address', 'outputs__address').order_by('-time')[:100]
        
        logger.info(f"Tìm thấy {len(coinjoin_transactions)} giao dịch CoinJoin")
        
        # Nếu không có giao dịch CoinJoin, trả về dữ liệu mẫu
        if not coinjoin_transactions.exists():
            logger.warning("Không tìm thấy giao dịch CoinJoin nào trong database")
            return JsonResponse({
                'groups': [],
                'total_groups': 0,
                'total_transactions': 0,
                'message': 'Không có dữ liệu CoinJoin trong database. Vui lòng import dữ liệu trước.'
            })
        
        # Thu thập các nhóm địa chỉ
        address_groups = {}
        
        for tx in coinjoin_transactions:
            # Lấy các địa chỉ input và output của giao dịch
            input_addresses = set()
            output_addresses = set()
            
            for inp in tx.inputs.all():
                if inp.address:
                    input_addresses.add(inp.address.address)
            
            for out in tx.outputs.all():
                if out.address:
                    output_addresses.add(out.address.address)
            
            # Tạo nhóm cho giao dịch này
            group_id = f"coinjoin_{tx.hash[:8]}"
            
            # Tính số dư tổng của nhóm
            total_balance = 0
            for addr in input_addresses | output_addresses:
                try:
                    balance = calculate_address_balance(addr)
                    total_balance += balance
                except Exception as e:
                    logger.warning(f"Không thể tính số dư cho địa chỉ {addr}: {str(e)}")
            
            # Tạo clusters cho input addresses
            input_clusters = []
            if input_addresses:
                # Nhóm các địa chỉ input theo cluster (có thể là cùng một ví)
                input_cluster = {
                    'cluster_id': f"input_cluster_{tx.hash[:8]}",
                    'addresses': list(input_addresses),
                    'total_balance': sum([calculate_address_balance(addr) for addr in input_addresses if calculate_address_balance(addr) > 0]),
                    'address_count': len(input_addresses)
                }
                input_clusters.append(input_cluster)
            
            # Tạo clusters cho output addresses
            output_clusters = []
            if output_addresses:
                # Nhóm các địa chỉ output theo cluster
                output_cluster = {
                    'cluster_id': f"output_cluster_{tx.hash[:8]}",
                    'addresses': list(output_addresses),
                    'total_balance': sum([calculate_address_balance(addr) for addr in output_addresses if calculate_address_balance(addr) > 0]),
                    'address_count': len(output_addresses)
                }
                output_clusters.append(output_cluster)
            
            address_groups[group_id] = {
                'group_id': group_id,
                'transaction_hash': tx.hash,
                'transaction_time': tx.time.strftime('%Y-%m-%d %H:%M'),
                'input_addresses': list(input_addresses),
                'output_addresses': list(output_addresses),
                'input_clusters': input_clusters,
                'output_clusters': output_clusters,
                'total_addresses': len(input_addresses) + len(output_addresses),
                'total_balance': total_balance,
                'fee': tx.fee or 0,
                'anomaly_score': tx.anomaly_score or 0,
                'tags': tx.tags or 'None'
            }
        
        # Chuyển đổi thành list và sắp xếp
        groups_list = list(address_groups.values())
        groups_list.sort(key=lambda x: x['total_addresses'], reverse=True)
        
        logger.info(f"Tạo thành công {len(groups_list)} nhóm địa chỉ CoinJoin")
        
        return JsonResponse({
            'groups': groups_list,
            'total_groups': len(groups_list),
            'total_transactions': len(coinjoin_transactions)
        })
        
    except Exception as e:
        logger.error(f"Lỗi khi lấy nhóm địa chỉ CoinJoin: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)

def get_coinjoin_group_graph(request):
    """API để lấy dữ liệu đồ thị cho một nhóm địa chỉ CoinJoin."""
    try:
        data = json.loads(request.body)
        selected_addresses = data.get('addresses', [])
        group_id = data.get('group_id', '')
        
        if not selected_addresses:
            return JsonResponse({'error': 'Không có địa chỉ được chọn'}, status=400)
        
        # Lấy thông tin chi tiết của các địa chỉ
        addresses_data = []
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
        
        # Lấy các giao dịch liên quan đến các địa chỉ được chọn
        related_transactions = Transaction.objects.filter(
            Q(inputs__address__address__in=selected_addresses) | 
            Q(outputs__address__address__in=selected_addresses)
        ).prefetch_related('inputs__address', 'outputs__address').distinct()[:50]
        
        # Thêm các địa chỉ được chọn vào đồ thị
        input_addresses = []
        output_addresses = []
        
        for addr_str in selected_addresses:
            try:
                addr_obj = Address.objects.get(address=addr_str)
                balance = calculate_address_balance(addr_str)
                
                # Tạo cluster ID đơn giản dựa trên địa chỉ
                cluster_id = f"cluster_{addr_str[:8]}"
                
                color = get_address_color(addr_obj.tags)
                title = f"Địa chỉ: {addr_str}\nSố dư: {balance:.8f} BTC\nTags: {addr_obj.tags or 'None'}\nCluster: {cluster_id}"
                
                # Phân loại địa chỉ dựa trên vai trò trong giao dịch
                if any(tx.inputs.filter(address__address=addr_str).exists() for tx in related_transactions):
                    input_addresses.append(addr_str)
                    add_node(addr_str, f"{addr_str[:8]}...", 'input', color, title)
                else:
                    output_addresses.append(addr_str)
                    add_node(addr_str, f"{addr_str[:8]}...", 'output', color, title)
                
                # Thêm thông tin balance và tags vào node
                node = next((n for n in nodes if n['id'] == addr_str), None)
                if node:
                    node['balance'] = balance
                    node['tags'] = addr_obj.tags or 'None'
                
                addresses_data.append({
                    'address': addr_str,
                    'balance': balance,
                    'cluster_id': cluster_id,
                    'tags': addr_obj.tags or 'None',
                    'color': color
                })
                
            except Address.DoesNotExist:
                continue
        
        # Thêm các giao dịch liên quan vào đồ thị
        for tx in related_transactions:
            tx_label = f"{tx.hash[:8]}..."
            tx_title = f"Giao dịch: {tx.hash}\nThời gian: {tx.time}\nPhí: {tx.fee} sats\nTags: {tx.tags or 'None'}"
            color = get_transaction_color(tx.anomaly_score)
            
            add_node(tx.hash, tx_label, 'processing', color, tx_title)
            
            # Thêm thông tin tags vào node giao dịch
            node = next((n for n in nodes if n['id'] == tx.hash), None)
            if node:
                node['tags'] = tx.tags or 'None'
            
            # Thêm các cạnh từ địa chỉ input đến giao dịch
            for inp in tx.inputs.all():
                if inp.address and inp.address.address in selected_addresses:
                    edges.append({
                        'from': inp.address.address,
                        'to': tx.hash,
                        'arrows': 'to',
                        'title': f"Input từ {inp.address.address}"
                    })
            
            # Thêm các cạnh từ giao dịch đến địa chỉ output
            for out in tx.outputs.all():
                if out.address and out.address.address in selected_addresses:
                    edges.append({
                        'from': tx.hash,
                        'to': out.address.address,
                        'arrows': 'to',
                        'title': f"Output đến {out.address.address}"
                    })
        
        # Thêm các địa chỉ liên quan khác (không phải địa chỉ được chọn)
        for tx in related_transactions:
            # Thêm các địa chỉ input khác
            for inp in tx.inputs.all():
                if inp.address and inp.address.address not in selected_addresses:
                    addr_str = inp.address.address
                    try:
                        addr_obj = Address.objects.get(address=addr_str)
                        balance = calculate_address_balance(addr_str)
                        color = get_address_color(addr_obj.tags)
                        title = f"Địa chỉ liên quan: {addr_str}\nSố dư: {balance:.8f} BTC\nTags: {addr_obj.tags or 'None'}"
                        
                        add_node(addr_str, f"{addr_str[:8]}...", 'input', color, title)
                        
                        # Thêm thông tin balance và tags vào node
                        node = next((n for n in nodes if n['id'] == addr_str), None)
                        if node:
                            node['balance'] = balance
                            node['tags'] = addr_obj.tags or 'None'
                        
                        # Thêm cạnh từ địa chỉ liên quan đến giao dịch
                        edges.append({
                            'from': addr_str,
                            'to': tx.hash,
                            'arrows': 'to',
                            'title': f"Input từ {addr_str}"
                        })
                    except Address.DoesNotExist:
                        continue
            
            # Thêm các địa chỉ output khác
            for out in tx.outputs.all():
                if out.address and out.address.address not in selected_addresses:
                    addr_str = out.address.address
                    try:
                        addr_obj = Address.objects.get(address=addr_str)
                        balance = calculate_address_balance(addr_str)
                        color = get_address_color(addr_obj.tags)
                        title = f"Địa chỉ liên quan: {addr_str}\nSố dư: {balance:.8f} BTC\nTags: {addr_obj.tags or 'None'}"
                        
                        add_node(addr_str, f"{addr_str[:8]}...", 'output', color, title)
                        
                        # Thêm thông tin balance và tags vào node
                        node = next((n for n in nodes if n['id'] == addr_str), None)
                        if node:
                            node['balance'] = balance
                            node['tags'] = addr_obj.tags or 'None'
                        
                        # Thêm cạnh từ giao dịch đến địa chỉ liên quan
                        edges.append({
                            'from': tx.hash,
                            'to': addr_str,
                            'arrows': 'to',
                            'title': f"Output đến {addr_str}"
                        })
                    except Address.DoesNotExist:
                        continue
        
        return JsonResponse({
            'success': True,
            'group_id': group_id,
            'addresses': addresses_data,
            'nodes': nodes,
            'edges': edges,
            'total_transactions': len(related_transactions)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dữ liệu JSON không hợp lệ'}, status=400)
    except Exception as e:
        logger.error(f"Lỗi khi lấy đồ thị nhóm CoinJoin: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Lỗi nội bộ máy chủ: {str(e)}'}, status=500)