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
│       └── optimizer
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

## Excel 导入导出

已为以下管理对象提供 Excel 功能：

- 押运线路
- 机构
- 机构订单

在对应 admin 列表页可使用：

- `.../import-excel/` 导入
- `.../export-excel/` 导出
- `.../template-excel/` 下载导入样表（机构订单模板同时提供“宽表样例”和“长表样例”）

机构订单导入已兼容：
- 宽表（单行单订单，面额分列）
- 长表（多行单订单，按面额+数量，导入时自动聚合）

机构订单长表导入中，`订单编号` 与 `订单状态` 不再人工导入：
- 同一份Excel视为一个订单导入批次，订单编号由系统按 `ORDYYYYMMDD-序号` 自动生成
- 同一份Excel仅支持一个订单日期（多日期请拆分导入）
- 订单状态由系统统一初始化为 `NEW`
- Excel 每一行作为一条订单导入明细保存
- 后台“订单管理”可查看每次导入批次及其明细
- 纸币拆分规则：超过20捆按“人工包(20捆/包)”拆分；余量进入流水线并按“16捆/箱”拆分
- 后台新增两个列表：
  - 人工清单（支持按日期/机构/面额汇总导出）
  - 流水线箱清单（供自动化执行，支持导出）
- 阈值配置改为主数据下“全局配置”统一编辑保存：
  - 走人工捆数阈值(捆)（默认20）
  - 流水线单箱捆数上限(捆)（默认16）
  - 流水线单箱捆数上限对同一订单下所有纸币面额共用，不按单个面额单独计算
  - 英文配置键由系统内部维护，后台不暴露编辑

主数据中可维护“面额封装规格”（如100元=1000张/捆，1元=500枚/包），机构订单长表导入支持填写“金额”，系统会按规格自动换算包/捆数。

导入订单时会校验面额绑定关系：必须同时存在“面额封装规格”和“工位支持面额”配置，否则拒绝导入。

管理后台首页新增“概览”模块（置顶），可进入流水线示意图页面查看工位流程与传输段时间。
