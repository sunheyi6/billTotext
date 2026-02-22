/**
 * Bilibili API 中转服务
 * 解决小程序 403 问题 + 缓存优化
 */
const express = require('express');
const axios = require('axios');
const NodeCache = require('node-cache');

const app = express();
const cache = new NodeCache({ stdTTL: 300 }); // 缓存5分钟

// B站请求头配置
const BILI_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Referer': 'https://space.bilibili.com',
  'Origin': 'https://space.bilibili.com',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
  'Accept-Encoding': 'gzip, deflate, br',
  'Connection': 'keep-alive',
};

// CORS 配置 - 允许小程序访问
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

app.use(express.json());

/**
 * 获取UP主信息
 * GET /api/up-info?mid=xxx
 */
app.get('/api/up-info', async (req, res) => {
  const { mid } = req.query;
  
  if (!mid) {
    return res.status(400).json({ code: -1, message: '缺少 mid 参数' });
  }

  const cacheKey = `up_info_${mid}`;
  
  // 检查缓存
  const cached = cache.get(cacheKey);
  if (cached) {
    console.log(`[Cache Hit] UP主 ${mid}`);
    return res.json({ ...cached, fromCache: true });
  }

  try {
    console.log(`[API Request] 获取UP主 ${mid}`);
    
    // 使用 B站 API
    const response = await axios.get('https://api.bilibili.com/x/space/wbi/acc/info', {
      params: { mid },
      headers: BILI_HEADERS,
      timeout: 10000,
      // 如果需要登录态，在这里添加 cookie
      // headers: { ...BILI_HEADERS, 'Cookie': 'SESSDATA=xxx' }
    });

    const data = response.data;
    
    if (data.code === 0) {
      // 缓存成功结果
      cache.set(cacheKey, data);
      console.log(`[Success] UP主 ${mid}: ${data.data?.name}`);
    } else {
      console.log(`[Bili API Error] code=${data.code}, message=${data.message}`);
    }
    
    res.json(data);
    
  } catch (error) {
    console.error('[Request Error]', error.message);
    
    // 详细的错误信息
    res.status(500).json({
      code: -500,
      message: '请求失败',
      error: error.message,
      // 返回缓存数据（如果有）
      staleData: cache.get(cacheKey)
    });
  }
});

/**
 * 批量获取UP主信息
 * POST /api/up-info-batch
 * Body: { mids: [1, 2, 3] }
 */
app.post('/api/up-info-batch', async (req, res) => {
  const { mids } = req.body;
  
  if (!Array.isArray(mids) || mids.length === 0) {
    return res.status(400).json({ code: -1, message: ' mids 必须是数组' });
  }

  if (mids.length > 50) {
    return res.status(400).json({ code: -1, message: '单次最多查询50个UP主' });
  }

  const results = [];
  const errors = [];

  // 串行请求避免触发风控
  for (const mid of mids) {
    try {
      const cacheKey = `up_info_${mid}`;
      let data = cache.get(cacheKey);
      
      if (!data) {
        const response = await axios.get('https://api.bilibili.com/x/space/wbi/acc/info', {
          params: { mid },
          headers: BILI_HEADERS,
          timeout: 10000,
        });
        data = response.data;
        if (data.code === 0) {
          cache.set(cacheKey, data);
        }
        // 添加延时避免风控
        await new Promise(r => setTimeout(r, 200));
      }
      
      results.push({ mid, data });
    } catch (error) {
      errors.push({ mid, error: error.message });
    }
  }

  res.json({
    code: 0,
    data: results,
    errors: errors.length > 0 ? errors : undefined,
    cached: results.filter(r => cache.get(`up_info_${r.mid}`)).length
  });
});

/**
 * 获取视频信息
 * GET /api/video-info?bvid=BV1xx411c7mD
 */
app.get('/api/video-info', async (req, res) => {
  const { bvid, aid } = req.query;
  
  if (!bvid && !aid) {
    return res.status(400).json({ code: -1, message: '需要 bvid 或 aid 参数' });
  }

  const cacheKey = `video_info_${bvid || aid}`;
  const cached = cache.get(cacheKey);
  if (cached) {
    return res.json({ ...cached, fromCache: true });
  }

  try {
    const params = bvid ? { bvid } : { aid };
    const response = await axios.get('https://api.bilibili.com/x/web-interface/view', {
      params,
      headers: BILI_HEADERS,
      timeout: 10000,
    });

    const data = response.data;
    if (data.code === 0) {
      cache.set(cacheKey, data);
    }
    
    res.json(data);
  } catch (error) {
    res.status(500).json({
      code: -500,
      message: '请求失败',
      error: error.message
    });
  }
});

/**
 * 健康检查
 */
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    cacheKeys: cache.keys().length,
    timestamp: new Date().toISOString()
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Bilibili Proxy Server running on port ${PORT}`);
  console.log(`📊 Test: http://localhost:${PORT}/api/up-info?mid=208259`);
});

module.exports = app;
