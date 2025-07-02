# **Bitcoin Tracker \- Trình truy vết và phân tích giao dịch Bitcoin**

**Bitcoin Tracker** là một ứng dụng web được phát triển bởi nhóm **KMABT (KMA Blockchain Tracer)**. Dự án được xây dựng bằng Django để nhập, phân tích và trực quan hóa dữ liệu từ một blockchain, nhằm mục đích truy vết các giao dịch và cung cấp cái nhìn sâu sắc về chúng.

## **✨ Tính năng chính**

* **Nhập dữ liệu Block**: Tải và xử lý dữ liệu blockchain từ các tệp JSON.  
* **Phân tích Heuristics**: Áp dụng các thuật toán heuristics để phân tích và gom cụm dữ liệu giao dịch, giúp phát hiện các mẫu và mối quan hệ.  
* **Trực quan hóa Dữ liệu**: Hiển thị danh sách giao dịch và các biểu đồ đồ thị (graph) trực quan để dễ dàng truy vết và hiểu rõ luồng dữ liệu.  
* **Giao diện Web**: Cung cấp giao diện web thân thiện và dễ sử dụng để người dùng tương tác với ứng dụng.  
* **Quản lý người dùng**: Hệ thống đăng ký và đăng nhập cơ bản cho người dùng.

## **📂 Cấu trúc Dự án**

Dưới đây là mô tả ngắn về các thành phần chính trong thư mục dự án.
```
.  
├── blockchain/              # Thư mục dự án Django chính  
│   ├── bitcoin/             # App xử lý logic liên quan đến Bitcoin (models, views, v.v.)  
│   ├── blockchain/          # App quản lý cấu hình project Django (chứa settings.py, urls.py gốc)  
│   ├── guide_page/          # App cho các trang hướng dẫn và thông tin  
│   ├── import_data/         # App chứa logic nhập dữ liệu từ các nguồn bên ngoài  
│   └── user/                # App quản lý người dùng (đăng ký, đăng nhập, hồ sơ)  
│   └── manage.py
├── data/                    # Thư mục chứa các tệp dữ liệu block thô (ví dụ: JSON)  
├── manage.py                # Tiện ích dòng lệnh của Django để quản lý dự án  
├── block_898421.json        # File dữ liệu block đầu vào mẫu  
├── README.md                # File hướng dẫn này  
├── LICENSE.md                  # File giấy phép của dự án  
└── requirements.txt         # Danh sách các thư viện Python cần thiết cho dự án
```
## **🚀 Bắt đầu**

Để cài đặt và chạy dự án trên máy của bạn, hãy làm theo các bước dưới đây.

### **Yêu cầu**

* [Python 3.8+](https://www.python.org/downloads/)  
* [pip](https://pip.pypa.io/en/stable/installation/) (thường được cài sẵn với Python)

### **Hướng dẫn Cài đặt**

1. **Clone repository về máy:**
```
git clone https://github.com/nghiaugust/blockchain\_truyvet.git
cd blockchain_truyvet
```
2. Cài đặt các thư viện cần thiết trong project:  
```
pip install -r requirements.txt
```
3. **Cấu hình Database:**  
   Tạo một database mới với tên blockchain\_truyvet.  
   Mở file blockchain/blockchain/settings.py và cập nhật thông tin database như tên, người dùng, mật khẩu

```
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'blockchain_truyvet',  # Thay bằng tên database của bạn
        'USER': 'root',  # Thay bằng user MySQL của bạn
        'PASSWORD': 'root',  # Thay bằng mật khẩu
        'HOST': 'localhost',
        'PORT': '3306',  # Cổng mặc định MySQL
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
```

4. Áp dụng Migration:  
   Tạo các bảng cần thiết trong database.  
   python manage.py migrate

5. Nhập dữ liệu ban đầu:  
   Chạy lệnh sau để nhập dữ liệu từ file block\_898421.json. Đảm bảo file này nằm trong thư mục data/.  
```
python manage.py import\_block\_data data/block\_898421.json
```

6. **Chạy phân tích Heuristics:**  
```
python manage.py heuristics \--chunk-size 1000
```

## **🎮 Sử dụng**

Khởi động server Django:

```
python manage.py runserver  
# Hoặc, nếu chạy với SSL (yêu cầu django-sslserver):  
# python manage.py runsslserver
```

Bây giờ bạn có thể truy cập ứng dụng web qua các đường dẫn sau:

* **Danh sách Giao dịch**: [http://127.0.0.1:8000/list-tx/](http://127.0.0.1:8000/list-tx/)  
* **Đồ thị tổng quan**: [http://127.0.0.1:8000/graph/](http://127.0.0.1:8000/graph/)  
* **Đồ thị Giao dịch**: [http://127.0.0.1:8000/tx-graph/](http://127.0.0.1:8000/tx-graph/)  
* **Trang nhập dữ liệu (nếu có giao diện web)**: [http://127.0.0.1:8000/import\_data/](http://127.0.0.1:8000/import_data/)

## **👥 Đội ngũ phát triển**

Dự án này được xây dựng và duy trì bởi nhóm **KMABT (KMA Blockchain Tracer)**.

## **📄 Giấy phép**

Bản quyền © 2025 KMABT (KMA Blockchain Tracer).

Dự án này được cấp phép theo Giấy phép MIT. Xem file [LICENSE](https://github.com/nghiaugust/blockchain_truyvet/blob/main/LICENSE.md) để biết thêm chi tiết.

## **📧 Liên hệ**

Nếu bạn có bất kỳ câu hỏi hoặc đề xuất nào, vui lòng mở một vấn đề (issue) trên GitHub hoặc liên hệ với chúng tôi tại [domanhnghiaforwork@gmail.com](mailto:domanhnghiaforwork@gmail.com).