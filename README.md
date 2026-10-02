# 灯具商城课程项目

目前完成 M1 基础骨架：FastAPI 后端、身份与角色数据库迁移、客户注册登录、管理员/商家端登录入口、三端最小页面。商品、报价、订单和以图搜图属于后续阶段，已有 [需求说明](文档/灯具商城需求规格说明书_v0.1.docx)、[系统设计](文档/灯具商城系统设计说明书_v0.1.docx)、[完整数据库规划](database/schema.sql) 和 [OpenAPI 契约](api/openapi-v0.1.yaml)。

## 本地启动

在 Windows PowerShell 中，先进入 `apps/api`。使用 Python 3.12 或 3.13：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端默认使用 `apps/api/.local/lamp_mall.db`，可通过 `DATABASE_URL` 指向 MySQL 8。使用 MySQL 时先创建空的 `lamp_mall` 数据库并确保账号有建表权限，再运行 Alembic。`database/schema.sql` 是全部 23 张表的设计基线，M1 迁移只创建 `users`、`roles`、`user_roles`，后续模块逐步纳入迁移；不要同时执行全量 SQL 和 M1 迁移。

访问 `http://127.0.0.1:8000/health/live` 和 `/health/ready` 检查服务；接口调试页为 `http://127.0.0.1:8000/api/docs`。

本地客户注册使用演示验证码 `123456`，可通过 `DEV_VERIFICATION_CODE` 改写。验证码仅在 `APP_ENV=local/test` 有效；`APP_ENV=production` 需要接入短信服务后才能开放注册。生产环境必须提供至少 32 字符的 `JWT_SECRET`。本地未显式设置密钥时，服务每次重启都会生成新密钥，旧令牌随之失效。

管理员与本地演示商家账号通过交互式命令创建，密码不会出现在命令参数或仓库里：

```powershell
python -m app.bootstrap_admin --username admin
python -m app.bootstrap_demo_merchant --username merchant-demo
```

分别进入 `apps/admin-web`、`apps/customer-mini`、`apps/merchant-mini` 执行 `npm install` 与 `npm run dev` 或 `npm run dev:h5`。默认本地地址是管理端 `5173`、客户端 H5 `5174`、商家端 H5 `5175`。两个 uni-app 项目可运行 `npm run dev:mp-weixin` 编译微信小程序；正式预览前在各自的 `src/manifest.json` 中填写自己申请的微信 AppID，并将 `VITE_API_BASE_URL` 设置为手机可访问的 HTTPS 接口地址。微信小程序还需在平台配置合法 request 域名。

## 验证

在 `apps/api` 下运行：

```powershell
python -m pytest -q tests
```

测试使用临时 SQLite 数据库执行真实迁移，验证注册重复、错误凭证、令牌失效、管理员/商家角色隔离和账号禁用。

## M1 边界与下一阶段

此版本的三个前端页面完成登录与身份展示，商家正式入驻认证、商品/SKU/报价审核、交易和图像检索尚未实现。下一阶段按系统设计的 M2 开发商品与报价闭环；商家端的本地演示账号只证明身份与权限链路，不代表已通过营业执照审核。

