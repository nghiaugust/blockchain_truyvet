1. pip install django

2. tạo database tên: blockchain_truyvet
    đổi mật khẩu trong setting.py

3. tạo ánh xạ model sang database bằng lệnh: python manage.py makemigrations
4. tạo database bằng: python manage.py makemigrations
5. cd blockchain_truyvet
6. chạy lệnh để thêm dữ liệu: python blockchain\manage.py import_block_data block_898421.json 
7. áp dụng heu: python manage.py heuristics --chunk-size 1000
8. python manage.py runserver

http://127.0.0.1:8000/list-tx/
http://127.0.0.1:8000/graph/
http://127.0.0.1:8000/tx-graph/