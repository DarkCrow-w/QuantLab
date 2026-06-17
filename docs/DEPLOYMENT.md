# QuantLab 部署指南

本文档描述生产化部署骨架。默认形态是：

- `backend`：FastAPI + Uvicorn，端口 `8001`
- `frontend`：Nginx 静态托管 React 构建产物，并反代 `/api`
- `quantlab-data`：Docker volume，保存行情缓存、研究资产、数据任务记录

## 1. 准备配置

```bash
cp config/quant.prod.env.example config/quant.env
```

按需填写：

- `TUSHARE_TOKEN`
- `DEEPSEEK_API_KEY` 或 `ANTHROPIC_API_KEY`
- `FUTU_HOST` / `FUTU_PORT`
- `QUANT_CORS_ORIGINS`

不要把 `config/quant.env` 提交到 Git。

## 2. 本地校验

```bash
python scripts/verify_deployment_config.py
python scripts/verify_clone_start.py
```

第一个命令校验 Docker、Nginx、Compose 和生产环境模板；第二个命令校验后端导入、测试和前端生产构建。

## 3. 启动容器

```bash
docker compose up --build -d
```

访问：

- 控制台：`http://127.0.0.1:8080`
- 健康检查：`http://127.0.0.1:8080/api/health`
- API 文档：`http://127.0.0.1:8080/docs`

## 4. 运维命令

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart backend
docker compose down
```

保留数据：

```bash
docker compose down
```

清空数据：

```bash
docker compose down -v
```

## 5. 上线前检查

1. 系统总览页的必需检查没有 `ERROR`。
2. 数据平台至少有常用标的缓存。
3. 研究资产页能看到回测实验记录。
4. 交易运行页显示实盘配置通过静态检查。
5. 实盘交易仍使用人工启动命令，不通过 Web UI 自动下单。
6. 外网部署时请在反向代理或网关层增加 HTTPS 和访问控制。

## 6. 边界说明

当前部署骨架适合单机或小团队内网环境。真正公网生产环境还需要：

- HTTPS 证书与域名网关
- 登录、权限和审计
- 数据库备份策略
- 监控告警
- 多实例任务锁和队列
