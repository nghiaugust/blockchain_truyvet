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
from .models import WalletAddress, UserProfile
from bitcoin.models import Address, TxOutput  # Import để tính số dư
from django.db.models import Sum
import json
import re
from django.http import HttpResponseRedirect



def calculate_address_balance(bitcoin_address):
    """
    Hàm tính số dư của một địa chỉ Bitcoin
    """
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
    

def register_view(request):
    """
    View xử lý đăng ký người dùng
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
          # Kiểm tra dữ liệu đầu vào
        if not all([username, email, password1, password2]):
            messages.error(request, 'Vui lòng điền đầy đủ thông tin')
            return render(request, 'user/register.html')
        
        if password1 != password2:
            messages.error(request, 'Mật khẩu không khớp')
            return render(request, 'user/register.html')
        
        if len(password1) < 8:
            messages.error(request, 'Mật khẩu phải có ít nhất 8 ký tự')
            return render(request, 'user/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email đã được sử dụng')
            return render(request, 'user/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Tên đăng nhập đã được sử dụng')
            return render(request, 'user/register.html')
        
        try:
            with transaction.atomic():
                # Tạo người dùng mới
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1
                )
                
                # Tạo hồ sơ người dùng
                UserProfile.objects.create(user=user)
                
                messages.success(request, 'Đăng ký thành công! Vui lòng đăng nhập.')
                return redirect('user:login')
                
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra: {str(e)}')
    
    return render(request, 'user/register.html')


def login_view(request):
    """
    View xử lý đăng nhập người dùng
    """
    if request.user.is_authenticated:
        return redirect('user:wallet')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not email or not password:
            messages.error(request, 'Vui lòng điền email và mật khẩu')            
            return render(request, 'user/login.html')
        
        # Xác thực người dùng bằng email
        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Chào mừng {user.email}!')
                return redirect('user:wallet')
            else:
                messages.error(request, 'Email hoặc mật khẩu không đúng')
        except User.DoesNotExist:
            messages.error(request, 'Email hoặc mật khẩu không đúng')
    
    return render(request, 'user/login.html')


def logout_view(request):
    """
    View xử lý đăng xuất người dùng
    """
    logout(request)
    messages.success(request, 'Đăng xuất thành công')
    return redirect('user:login')


@login_required
def wallet_view(request):
    """
    View chính hiển thị ví cho người dùng đã đăng nhập
    """
    user = request.user
    
    # Lấy hoặc tạo hồ sơ người dùng
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Lấy danh sách địa chỉ ví của người dùng
    wallet_addresses = WalletAddress.objects.filter(user=user, is_active=True)
    
    # Tính tổng số dư
    total_balance = sum(addr.balance for addr in wallet_addresses)
    
    # Cập nhật tổng số dư trong hồ sơ
    if profile.total_balance != total_balance:
        profile.total_balance = total_balance
        profile.save()
    
    context = {
        'user': user,
        'profile': profile,
        'wallet_addresses': wallet_addresses,
        'total_balance': total_balance,
        'primary_address': wallet_addresses.filter(is_primary=True).first(),
    }
    
    return render(request, 'user/wallet_user.html', context)


@login_required
@require_http_methods(["POST"])
def add_wallet_address(request):
    """
    Thêm địa chỉ ví mới cho người dùng
    """
    try:
        data = json.loads(request.body)
        address = data.get('address', '').strip()
        label = data.get('label', '').strip()
        address_type = data.get('address_type', 'P2PKH')
        is_primary = data.get('is_primary', False)
        
        # Kiểm tra định dạng địa chỉ Bitcoin (kiểm tra cơ bản)
        if not address:
            return JsonResponse({'success': False, 'error': 'Địa chỉ ví không được để trống'})
        
        if len(address) < 26 or len(address) > 62:
            return JsonResponse({'success': False, 'error': 'Địa chỉ ví không hợp lệ'})
        
        # Kiểm tra xem địa chỉ đã tồn tại chưa
        if WalletAddress.objects.filter(address=address).exists():
            return JsonResponse({'success': False, 'error': 'Địa chỉ ví đã tồn tại'})
        
        # Tính số dư từ dữ liệu giao dịch
        calculated_balance = calculate_address_balance(address)
        
        # Tạo địa chỉ ví mới với số dư đã tính
        wallet_address = WalletAddress.objects.create(
            user=request.user,
            address=address,
            label=label,
            address_type=address_type,
            is_primary=is_primary,
            balance=calculated_balance  # Lưu số dư đã tính
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Thêm địa chỉ ví thành công',
            'address': {
                'id': wallet_address.id,
                'address': wallet_address.address,
                'label': wallet_address.label,
                'address_type': wallet_address.address_type,
                'is_primary': wallet_address.is_primary,
                'balance': str(wallet_address.balance),
                'created_at': wallet_address.created_at.isoformat()
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Dữ liệu không hợp lệ'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Có lỗi xảy ra: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def delete_wallet_address(request, address_id):
    """
    Xóa một địa chỉ ví
    """
    try:
        wallet_address = get_object_or_404(WalletAddress, id=address_id, user=request.user)
        
        if wallet_address.is_primary:
            return JsonResponse({'success': False, 'error': 'Không thể xóa địa chỉ ví chính'})
        
        wallet_address.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Xóa địa chỉ ví thành công'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Có lỗi xảy ra: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def set_primary_address(request, address_id):
    """
    Đặt một địa chỉ ví làm địa chỉ chính
    """
    try:
        wallet_address = get_object_or_404(WalletAddress, id=address_id, user=request.user)
        
        # Xóa trạng thái chính khỏi các địa chỉ khác
        WalletAddress.objects.filter(user=request.user).update(is_primary=False)
        
        # Đặt địa chỉ này làm chính
        wallet_address.is_primary = True
        wallet_address.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Đặt làm địa chỉ ví chính thành công'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Có lỗi xảy ra: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def refresh_address_balance(request, address_id):
    """
    Cập nhật lại số dư cho một địa chỉ ví cụ thể
    """
    try:
        wallet_address = get_object_or_404(WalletAddress, id=address_id, user=request.user)
        
        # Tính lại số dư
        old_balance = wallet_address.balance
        new_balance = calculate_address_balance(wallet_address.address)
        
        # Cập nhật vào database
        wallet_address.balance = new_balance
        wallet_address.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Cập nhật số dư thành công',
            'address': wallet_address.address,
            'old_balance': str(old_balance),
            'new_balance': str(new_balance),
            'difference': str(new_balance - old_balance)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Có lỗi xảy ra: {str(e)}'})


@login_required
def profile_view(request):
    """
    View hiển thị và chỉnh sửa hồ sơ người dùng
    """
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Cập nhật thông tin hồ sơ
        profile.bio = request.POST.get('bio', '')
        profile.location = request.POST.get('location', '')
        profile.preferred_currency = request.POST.get('preferred_currency', 'BTC')
        profile.notifications_enabled = request.POST.get('notifications_enabled') == 'on'
        
        # Cập nhật thông tin người dùng
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.phone_number = request.POST.get('phone_number', '')
        
        try:
            profile.save()
            request.user.save()
            messages.success(request, 'Cập nhật thông tin thành công')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra: {str(e)}')
        
        return redirect('user:profile')
    
    context = {
        'profile': profile,
        'user': request.user
    }
    
    return render(request, 'user/profile.html', context)

def home_redirect_view(request):
    """
    Chuyển hướng trang gốc: nếu đăng nhập thì đến ví, không thì đến đăng nhập.
    """
    if request.user.is_authenticated:
        return redirect('user:wallet')
    return redirect('user:login')
