1. pip install django

2. tạo database tên: blockchain_truyvet
   đổi mật khẩu trong setting.py

3. Áp dụng migration vào database: python manage.py migrate
   (Lưu ý: Không cần makemigrations vì file migration đã có sẵn trong project)
4. cd blockchain_truyvet
5. chạy lệnh để thêm dữ liệu: python blockchain\manage.py import_block_data block_898421.json
6. áp dụng heu: python manage.py heuristics --chunk-size 1000
7. python manage.py runserver

http://127.0.0.1:8000/list-tx/
http://127.0.0.1:8000/graph/
http://127.0.0.1:8000/tx-graph/
