# 灯具商城课程项目

目前完成 M1 基础骨架和 M2 商品报价流程：客户/商家账号、商家认证、受控图片上传、商品与多规格、商品/报价审核、上下架、多商家报价、客户端分类/搜索/详情。订单和以图搜图尚未实现。已有 [需求说明](文档/灯具商城需求规格说明书_v0.1.docx)、[系统设计](文档/灯具商城系统设计说明书_v0.1.docx)、[完整数据库规划](database/schema.sql) 和 [M2 演示说明](文档/M2开发与演示.md)。

`api/openapi-v0.1.yaml` 是包含后续阶段的设计基线；当前已实现接口以 [openapi-m2.json](api/openapi-m2.json) 和运行时 `/api/openapi.json` 为准。

## 本地启动

在 Windows PowerShell 中，先进入 `apps/api`。使用 Python 3.12 或 3.13：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端默认使用 `apps/api/.local/lamp_mall.db`，可通过 `DATABASE_URL` 指向 MySQL 8。使用 MySQL 时先创建空的 `lamp_mall` 数据库并确保账号有建表权限，再运行 Alembic。当前 M1+M2 迁移共创建 14 张业务表（另有 Alembic 版本表），自动初始化三类角色和五类灯具分类。`database/schema.sql` 保留为完整 23 表的设计基线；请只使用 Alembic 升级运行数据库，不要同时执行全量 SQL。MySQL 实机测试尚未执行，当前集成测试使用 SQLite。

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

生成 3 件灯具、2 家店铺的 6 条报价及管理员/商家/客户共 4 个账号。随机密码写入 `.local/demo-accounts.json`，不会上传 GitHub。仅允许 `APP_ENV=local`；再次运行会检测既有演示账号并停止，不覆盖既有数据。演示图片为程序绘制的灯具示意图，不是图像检索评估数据。新商家也可以在商家端注册并提交认证申请。

## 验证

在 `apps/api` 下运行：

```powershell
python -m pytest -q -p no:cacheprovider tests
```

测试使用临时 SQLite 数据库和上传目录执行真实迁移，验证注册登录、权限隔离、文件校验与私有访问、审核/驳回/重提、版本冲突、多商家报价、唯一有效报价、上下架与搜索过滤。关闭 pytest 缓存是为了兼容受限目录环境。

管理端运行 `npm run build`；两个小程序分别运行 `npm run build:h5`、`npm run build:mp-weixin` 和 `npx tsc --noEmit`。项目根目录可运行 `python tools/export_openapi.py` 重新导出已实现的接口契约。

## 当前边界与下一阶段

M2 的认证审核由管理员人工决定，演示认证不代表真实营业资质校验。图片存放在本机 `.local/uploads`，上传时检查类型/体积/像素并重新编码；证照始终私有，商品图只有关联商品上架后才允许匿名读取。生产对象存储、短信服务、上传病毒扫描、MySQL 实机验收及微信真机验收仍需接入或验证。管理与商家列表当前适用于课程演示规模。

下一阶段为 M3：下单、价格快照、库存处理、商家确认、发货和完成；随后为 M4：真实图片数据、检索基线、索引和可复现评估。
