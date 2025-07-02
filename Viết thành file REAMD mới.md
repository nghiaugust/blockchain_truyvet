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

.  
├── blockchain/                 \# Thư mục dự án Django chính  
│   ├── bitcoin/                \# App xử lý logic liên quan đến Bitcoin (models, views, v.v.)  
│   ├── blockchain/             \# App quản lý cấu hình project Django (chứa settings.py, urls.py gốc)  
│   ├── guide\_page/             \# App cho các trang hướng dẫn và thông tin  
│   ├── import\_data/            \# App chứa logic nhập dữ liệu từ các nguồn bên ngoài  
│   └── user/                   \# App quản lý người dùng (đăng ký, đăng nhập, hồ sơ)  
│   └── manage.py  
├── data/                       \# Thư mục chứa các tệp dữ liệu block thô (ví dụ: JSON)  
├── manage.py                   \# Tiện ích dòng lệnh của Django để quản lý dự án  
├── block\_898421.json           \# File dữ liệu block đầu vào mẫu  
├── README.md                   \# File hướng dẫn này  
├── LICENSE.md                  \# File giấy phép của dự án  
└── requirements.txt            \# Danh sách các thư viện Python cần thiết cho dự án

## **🚀 Bắt đầu**

Để cài đặt và chạy dự án trên máy của bạn, hãy làm theo các bước dưới đây.

### **Yêu cầu**

* [Python 3.8+](https://www.python.org/downloads/)  
* [pip](https://pip.pypa.io/en/stable/installation/) (thường được cài sẵn với Python)  
* **MySQL Server**: Đảm bảo MySQL Server đã được cài đặt và đang chạy trên hệ thống của bạn. Bạn có thể tải xuống từ trang chính thức của MySQL: \[liên kết đáng ngờ đã bị xóa\]

### **Hướng dẫn Cài đặt**

1. **Clone repository về máy:**  
   git clone https://github.com/nghiaugust/blockchain\_truyvet.git  
   cd blockchain\_truyvet

2. Cài đặt các thư viện cần thiết trong project:  
   pip install \-r requirements.txt

3. **Thiết lập Database MySQL:**    **Tạo Database**    **Mở trình quản lý MySQL của bạn (ví dụ: MySQL Workbench, phpMyAdmin hoặc dòng lệnh MySQL client) và chạy lệnh sau để tạo một database mới:**    **CREATE DATABASE blockchain\_truyvet CHARACTER SET utf8mb4 COLLATE utf8mb4\_unicode\_ci;**     **Lệnh trên sẽ tạo một database có tên blockchain\_truyvet với bộ ký tự và đối chiếu hỗ trợ đầy đủ các ký tự Unicode.**    **Tạo người dùng và cấp quyền (Tùy chọn)**    **Để tăng cường bảo mật, bạn nên tạo một người dùng MySQL riêng biệt cho ứng dụng của mình thay vì sử dụng tài khoản root. Thay thế your\_username và your\_password bằng thông tin đăng nhập mong muốn của bạn:**    **CREATE USER 'your\_username'@'localhost' IDENTIFIED BY 'your\_password';**    **GRANT ALL PRIVILEGES ON blockchain\_truyvet.\* TO 'your\_username'@'localhost';**    **FLUSH PRIVILEGES;**     **Cấu hình Django Database**    **Mở file blockchain/blockchain/settings.py và cập nhật cấu hình DATABASES như sau, đảm bảo thay thế USER và PASSWORD nếu bạn đã tạo người dùng riêng:**    **DATABASES \= {**        **'default': {**            **'ENGINE': 'django.db.backends.mysql',**            **'NAME': 'blockchain\_truyvet',  \# Tên database bạn vừa tạo**            **'USER': 'your\_username',  \# Thay bằng user MySQL của bạn (ví dụ: 'root' hoặc 'your\_username')**            **'PASSWORD': 'your\_password',  \# Thay bằng mật khẩu MySQL của bạn (ví dụ: 'root' hoặc 'your\_password')**            **'HOST': 'localhost',**            **'PORT': '3306',  \# Cổng mặc định MySQL**            **'OPTIONS': {**                **'init\_command': "SET sql\_mode='STRICT\_TRANS\_TABLES'",**            **},**        **}**    **}** 

4. Áp dụng Migration:  
   Tạo các bảng cần thiết trong database.  
   python .\\blockchain\\manage.py migrate

5. Nhập dữ liệu ban đầu:  
   Chạy lệnh sau để nhập dữ liệu từ file block\_898421.json. Đảm bảo file này nằm trong thư mục data/.  
   python .\\blockchain\\manage.py import\_block\_data data/block\_898421.json

6. **Chạy phân tích Heuristics:**  
   python .\\blockchain\\manage.py heuristics \--chunk-size 1000

## **🎮 Sử dụng**

Khởi động server Django:

python .\\blockchain\\manage.py runserver  
\# Hoặc, nếu chạy với SSL (yêu cầu django-sslserver):  
\# python .\\blockchain\\manage.py runsslserver

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