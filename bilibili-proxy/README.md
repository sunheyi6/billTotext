# Bilibili API 中转服务

解决微信小程序访问 Bilibili API 403 问题的完整方案。

## 问题原因

1. **403 Forbidden**: B站 API 有 Referer/UA 校验，小程序直接请求会被拦截
2. **域名白名单**: 小程序只能访问配置的服务器域名，不能直接访问 bilibili.com
3. **风控限制**: 频繁请求会触发 B站 WAF 防护

## 解决方案架构

```
微信小程序 → 你的后端服务 → Bilibili API
                 ↓
            [Redis/内存缓存]
            [请求头伪装]
            [频率控制]
```

## 快速开始

### 1. 部署后端服务

```bash
cd bilibili-proxy
npm install
npm start
```

服务默认运行在 `http://localhost:3000`

### 2. 测试 API

```bash
# 查询 UP主信息 (老番茄)
curl "http://localhost:3000/api/up-info?mid=208259"

# 查询视频信息
curl "http://localhost:3000/api/video-info?bvid=BV1xx411c7mD"

# 批量查询
curl -X POST "http://localhost:3000/api/up-info-batch" \
  -H "Content-Type: application/json" \
  -d '{"mids": [208259, 546195]}'
```

### 3. 小程序配置

修改 `miniprogram/utils/bilibili.js` 中的 API_BASE：

```javascript
const API_BASE = 'https://your-domain.com';  // 你的后端域名
```

在微信公众平台 → 开发管理 → 开发设置 → 服务器域名中添加：
- request合法域名: `https://your-domain.com`

### 4. 导入小程序

使用微信开发者工具导入 `miniprogram` 目录。

## 部署到服务器

### 使用 PM2 (推荐)

```bash
npm install -g pm2
npm run pm2
```

### Docker 部署

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
```

```bash
docker build -t bilibili-proxy .
docker run -d -p 3000:3000 bilibili-proxy
```

### 云函数部署 (腾讯云/阿里云)

见 `cloud-function/` 目录 (可根据需要自行添加)。

## API 文档

### GET /api/up-info

获取 UP主信息

**参数:**
- `mid` (required): UP主 ID

**响应:**
```json
{
  "code": 0,
  "message": "0",
  "data": {
    "mid": 208259,
    "name": "老番茄",
    "face": "https://...",
    "sign": "...",
    "follower": 19000000,
    "following": 234,
    "level": 6
  }
}
```

### POST /api/up-info-batch

批量获取 UP主信息

**请求体:**
```json
{
  "mids": [208259, 546195]
}
```

### GET /api/video-info

获取视频信息

**参数:**
- `bvid`: BV号 (如 BV1xx411c7mD)
- `aid`: AV号 (可选)

## 优化特性

| 特性 | 说明 |
|------|------|
| 🚀 内存缓存 | 5分钟默认缓存，减少重复请求 |
| 🔄 自动重试 | 网络错误自动重试2次 |
| 📱 小程序缓存 | 本地存储二次缓存 |
| ⏱️ 频率控制 | 批量请求自动添加延时 |
| 🛡️ 请求头伪装 | 模拟浏览器请求 |
| 📊 健康检查 | `/health` 端点监控服务状态 |

## 常见问题

### 1. 后端返回 401/403

可能需要添加 SESSDATA Cookie (登录态)：

```javascript
const BILI_HEADERS = {
  ...BILI_HEADERS,
  'Cookie': 'SESSDATA=xxx; bili_jct=xxx'
};
```

获取方式：浏览器登录 B站 → F12 → Application → Cookies

### 2. 小程序请求失败

- 检查域名是否已配置到小程序后台
- 检查服务器是否支持 HTTPS (生产环境必须)
- 检查 SSL 证书是否有效

### 3. 请求超时

调整 `timeout` 参数：

```javascript
axios.get(url, { timeout: 30000 })  // 30秒
```

## 技术栈

- **后端**: Node.js + Express + Axios + Node-Cache
- **小程序**: 原生微信小程序
- **部署**: PM2 / Docker / 云函数

## License

MIT
