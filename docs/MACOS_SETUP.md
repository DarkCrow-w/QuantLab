# macOS 启动说明

QuantLab 在 macOS 上不需要 WSL。请先安装：

- Python 3.10、3.11 或 3.12
- Node.js LTS

推荐使用 Homebrew：

```bash
brew install python node
```

首次启动：

```bash
cd /path/to/Quant
chmod +x quant.sh start-mac.command stop-mac.command
./quant.sh start
```

启动器会自动完成：

- 从 `config/quant.env.example` 创建 `config/quant.env`
- 创建 `.venv`
- 安装 `requirements.txt`
- 安装前端依赖
- 启动 FastAPI 后端和 Vite 前端

默认地址：

- 前端：`http://localhost:5174`
- 后端文档：`http://localhost:8001/docs`

停止服务：

```bash
./quant.sh stop
```

也可以双击 `start-mac.command` 和 `stop-mac.command`。

如果 pip 下载慢或失败，可以先手动执行：

```bash
.venv/bin/python -m pip install --prefer-binary -r requirements.txt -i https://pypi.org/simple
```

国内网络可以改用：

```bash
.venv/bin/python -m pip install --prefer-binary -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
