# Python API 部署说明

## 1. 环境准备

### 安装 Python 3.8+

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip
```

### 创建虚拟环境（推荐）

```bash
cd backend_api_python
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 开发环境运行

```bash
python run.py
```

服务将在 `http://localhost:5000` 启动

## 3. 生产环境部署

### 使用 Gunicorn

```bash
# 安装 gunicorn（已在 requirements.txt 中）
pip install gunicorn

# 启动服务
gunicorn -c gunicorn_config.py "run:app"

# 或使用命令行参数
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 "run:app"
```

### 使用 Supervisor 管理进程

创建 `/etc/supervisor/conf.d/quantdinger_python_api.conf`:

```ini
[program:quantdinger_python_api]
command=/path/to/venv/bin/gunicorn -c /path/to/gunicorn_config.py "run:app"
directory=/path/to/backend_api_python
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/path/to/logs/supervisor.log
```

启动：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start quantdinger_python_api
```

### 使用 Systemd 管理服务

创建 `/etc/systemd/system/quantdinger-python-api.service`:

```ini
[Unit]
Description=QuantDinger Python API Service
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/backend_api_python
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -c /path/to/gunicorn_config.py "run:app"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable quantdinger-python-api
sudo systemctl start quantdinger-python-api
sudo systemctl status quantdinger-python-api
```

## 4. Nginx 反向代理配置

在 Nginx 配置文件中添加：

```nginx
upstream python_api {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80;
    server_name api-python.quantdinger.com;

    location / {
        proxy_pass http://python_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持（如果需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

## 5. PHP 配置
（已移除）本仓库当前不包含 PHP 网关/后台服务，前端开发环境通过 `quantdinger_vue/vue.config.js` 将 `/api` 代理到 Python 服务即可。

## 6. 日志管理

创建日志目录：

```bash
mkdir -p logs
chmod 755 logs
```

日志文件：
- `logs/access.log` - 访问日志
- `logs/error.log` - 错误日志
- `logs/gunicorn.pid` - Gunicorn 进程ID

## 7. 监控和健康检查

### 健康检查接口

```bash
curl http://localhost:5000/health
```

### 监控脚本示例

```bash
#!/bin/bash
# check_api.sh

API_URL="http://localhost:5000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)

if [ $RESPONSE -ne 200 ]; then
    echo "API 服务异常，状态码: $RESPONSE"
    # 发送告警通知
    # 重启服务
    systemctl restart quantdinger-python-api
fi
```

## 8. 常见问题

### AKSHARE 安装失败

```bash
# 可能需要安装系统依赖
sudo apt-get install build-essential
pip install akshare --upgrade
```

### 端口被占用

```bash
# 查看端口占用
lsof -i :5000
# 或
netstat -tulpn | grep 5000

# 修改端口
export PYTHON_API_PORT=5001
```

### 权限问题

```bash
# 确保日志目录有写权限
chown -R www-data:www-data logs/
chmod -R 755 logs/
```

## 9. 性能优化

1. **增加 Worker 数量**：根据 CPU 核心数调整
2. **使用异步 Worker**：`worker_class = "gevent"`（需要安装 gevent）
3. **启用缓存**：使用 Redis 缓存指数数据
4. **数据库连接池**：如果使用数据库，配置连接池

## 10. 安全建议

1. 使用 HTTPS
2. 配置防火墙规则
3. 限制 API 访问频率
4. 使用 API Key 认证（如果需要）
5. 定期更新依赖包

