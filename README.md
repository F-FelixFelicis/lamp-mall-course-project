# 灯具商城课程项目

目前完成 M1 基础骨架、M2 商品报价流程、M3 模拟订单履约及 M4 图搜功能集成：账号与权限、商家认证、商品/SKU/报价审核、上下架、多商家比价、分类/搜索/详情、地址与订单快照、库存处理、发货和已购评价，以及本地视觉特征检索、颜色基线、索引管理和三端图搜页面。M4 已运行真实排序及耗时实验，正式相关性指标仍待两人独立标注。已有 [需求分析报告](文档/灯具商城需求分析报告.docx)、[系统设计](文档/灯具商城系统设计说明书_v0.1.docx)、[完整数据库规划](database/schema.sql)、[M2 演示说明](文档/M2开发与演示.md)、[M3 开发与验收](文档/M3开发与验收.md) 和 [M4 算法与实验记录](文档/M4算法设计与实验记录.md)。

`api/openapi-v0.1.yaml` 是包含后续阶段的设计基线；当前已实现接口以 [openapi-m4.json](api/openapi-m4.json) 和运行时 `/api/openapi.json` 为准，M2/M3 JSON 保留为阶段契约。

## 本地启动

在 Windows PowerShell 中，先进入 `apps/api`。使用 Python 3.12 或 3.13：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端默认使用 `apps/api/.local/lamp_mall.db`，可通过 `DATABASE_URL` 指向 MySQL 8。使用 MySQL 时先创建空的 `lamp_mall` 数据库并确保账号有建表权限，再运行 Alembic。当前 M1–M4 迁移共创建 21 张业务表（另有 Alembic 版本表），自动初始化三类角色和五类灯具分类。已有本地演示数据库可在项目根目录运行 `python tools/upgrade_local_m4.py`，该命令先验证 SQLite 备份，再升级迁移并核对既有账号、商品、报价及订单数量。`database/schema.sql` 保留为完整 23 表的设计基线；请只使用 Alembic 升级运行数据库，不要同时执行全量 SQL。MySQL 实机测试尚未执行，当前集成测试使用 SQLite。

访问 `http://127.0.0.1:8000/health/live` 和 `/health/ready` 检查服务；接口调试页为 `http://127.0.0.1:8000/api/docs`。

本地客户注册使用演示验证码 `123456`，可通过 `DEV_VERIFICATION_CODE` 改写。验证码仅在 `APP_ENV=local/test` 有效；`APP_ENV=production` 需要接入短信服务后才能开放注册。生产环境必须提供至少 32 字符的 `JWT_SECRET`。本地未显式设置密钥时，服务每次重启都会生成新密钥，旧令牌随之失效。

管理员与本地演示商家账号通过交互式命令创建，密码不会出现在命令参数或仓库里：

```powershell
python -m app.bootstrap_admin --username admin
python -m app.bootstrap_demo_merchant --username merchant-demo
```

分别进入 `apps/admin-web`、`apps/customer-mini`、`apps/merchant-mini` 执行 `npm ci` 与 `npm run dev` 或 `npm run dev:h5`。默认本地地址是管理端 `5173`、客户端 H5 `5174`、商家端 H5 `5175`。两个 uni-app 项目可运行 `npm run dev:mp-weixin` 编译微信小程序；正式预览前在各自的 `src/manifest.json` 中填写自己申请的微信 AppID，并将 `VITE_API_BASE_URL` 设置为手机可访问的 HTTPS 接口地址。微信小程序还需配置合法 request、uploadFile 和 downloadFile 域名。

## 一次生成本地演示数据

在 `apps/api` 目录、完成迁移并安装开发依赖后运行：

```powershell
python -m app.seed_demo
```

生成 20 款灯具样式、2 家店铺的 40 条演示报价及管理员/商家/客户共 4 个账号。随机密码写入 `.local/demo-accounts.json`，不会上传 GitHub。仅允许 `APP_ENV=local`；再次运行会检测既有演示账号并停止，不覆盖既有数据。图片来自 Pexels / Unsplash，均记录作者、来源与使用许可，详见 [图片与定价说明](assets/catalog/README.md)。这批图片不是图像检索评估数据。新商家也可以在商家端注册并提交认证申请。

如果已经生成过旧版 3 款示意商品，在 `apps/api` 下执行 `python -m app.demo_catalog` 即可升级：先备份本地数据库，再添加 20 款实拍样式，下架旧 3 款但保留全部历史记录；不覆盖账号或其他商品。重复执行不重复创建，保留已经生效的报价和手动下架状态。升级命令仅支持默认本地 SQLite。

页面明确标注“演示价”，价格按灯型档位参考公开零售页面后人为设定，并非照片原商品的实际报价。未核验的尺寸、功率、材质等参数留空；当前仍不支持真实购买。

## 验证

在 `apps/api` 下运行：

```powershell
python -m pytest -q -p no:cacheprovider tests
```

测试使用临时 SQLite 数据库和上传目录执行真实迁移，验证注册登录、权限隔离、文件校验与私有访问、审核/驳回/重提、版本冲突、多商家报价、唯一有效报价、上下架与搜索过滤，并覆盖订单全流程、价格/地址快照、多商品事务回滚、重复提交、并发抢最后一件库存和重复取消。M4 还覆盖索引与可售状态同步、图搜请求校验、大图内存处理、模型预加载及人工标注规则；本地权重存在时运行真实 ResNet18 特征检查。关闭 pytest 缓存是为了兼容受限目录环境。

管理端运行 `npm run build`；两个小程序分别运行 `npm run build:h5`、`npm run build:mp-weixin` 和 `npx tsc --noEmit`。项目根目录可运行 `python tools/export_openapi.py` 重新导出已实现的接口契约。

## 当前边界与下一阶段

M2 的认证审核由管理员人工决定，演示认证不代表真实营业资质校验。图片存放在本机 `.local/uploads`，上传时检查类型/体积/像素并重新编码；证照始终私有，商品图只有关联商品上架后才允许匿名读取。生产对象存储、短信服务、上传病毒扫描、MySQL 实机验收及微信真机验收仍需接入或验证。管理与商家列表当前适用于课程演示规模。

M3 订单按“待确认 → 待发货 → 已发货 → 已完成”推进；商家拒绝或顾客发货前取消均转“已取消”并释放库存。无真实支付、退款或物流接口，发货信息用于演示。一单仅含同一商家的商品，顾客页面从单个报价直接下单，接口支持同店多项；购物车、多商家拆单和评价配图尚未实现。有待确认/待发货订单时，阻止替换该商家的对应 SKU 报价和修改该 SKU 规格，待履约或取消后再操作。

## 以图搜图启动与评测

后端安装 `requirements-image-search.txt`，使用匹配的 CPU PyTorch/TorchVision。项目根目录运行 `python tools/prepare_image_search_weights.py`，它校验并复制已有的官方 ResNet18 权重缓存；无缓存时按 [M4 说明](文档/M4算法设计与实验记录.md) 取得官方文件并用 `--source` 指定。API 运行时不会联网下载模型。

完成商品数据准备后，在 `apps/api` 运行 `python -m app.build_image_index`；也可在管理端“以图搜图”建立索引。正常启动会在已有模型和索引时预加载，首次启动需等待运行库加载；`IMAGE_SEARCH_PRELOAD=0` 可关闭预加载。顾客首页和商家工作台提供“图片找相似灯具”，支持整体外观/颜色分布两种排序及灯型过滤。查询原图与查询向量均不落盘，商品详情继续使用当前有效报价。

已固定 20 张图库与 15 张独立查询图，分为开发 5 张、测试 10 张。两名组员可以打开 [人工标注页面](assets/image_search_benchmark/annotation.html)，独立导出相关性记录，有分歧再由第三人裁定。运行 `python tools/evaluate_image_search.py --predict-only --split test` 仅导出真实 Top-5 和耗时，相关性指标为空；正式评测须提供已完成标注，详见 [评测说明](assets/image_search_benchmark/README.md)。

当前仍需完成人工相关性标注、正式 Recall@5/Precision@5 评测、失败样例复核，以及 MySQL 实机和微信真机验收。图搜结果是通用视觉相似候选，尚无灯具主体检测和经标注校准的无匹配阈值，不能保证同款或已达到需求报告建议目标。
