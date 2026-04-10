# jktest - 金库配钞排序优化项目

基于 **Django + MySQL + Docker Desktop(macOS)** 的配钞订单排序优化基础工程。

## 已实现内容

- 11 张核心业务表对应 Django 模型
- 新增两张能力扩展表：
  - 工位支持面额表 `station_denomination_support`
  - 工位面额效率表 `station_denomination_efficiency`
- `phpMyAdmin` 管理支持
- Django 在 gunicorn 下通过 WhiteNoise 提供静态文件（已包含 admin 样式）

## 目录结构

```text
.
├── docker-compose.yml
├── backend
│   ├── Dockerfile
│   ├── manage.py
│   ├── requirements.txt
│   ├── config
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── apps
│       ├── masterdata
│       ├── orders
│       ├── optimizer
│       └── runs
```

## 快速启动

```bash
docker compose up -d --build
```

访问地址：

- Django Admin: http://localhost:8000/admin
- phpMyAdmin: http://localhost:8080
  - Host: `mysql`
  - User: `root`
  - Password: `root123`

## 初始化（首次）

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

## 主要模型分布

- 主数据：`backend/apps/masterdata/models.py`
- 订单：`backend/apps/orders/models.py`
- 优化参数：`backend/apps/optimizer/models.py`
- 运行结果：`backend/apps/runs/models.py`
