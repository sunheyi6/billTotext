/**
 * Bilibili API 中转服务 (WBI 签名版本)
 * B站新版 API 需要 WBI 签名才能访问
 */
const express = require('express');
const axios = require('axios');
const NodeCache = require('node-cache');
const crypto = require('crypto');

const app = express();
const cache = new NodeCache({ stdTTL: 300 });

// WBI 签名常量
const WBIMixinKeyEncTab = [
  46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
  27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
  37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
  22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
];

// B站请求头
const BILI_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
  'Referer': 'https://space.bilibili.com',
  'Origin': 'https://space.bilibili.com',
  'Accept': 'application/json, text/plain, */*',
};

let cachedWbiKeys = null;
let wbiKeysExpireTime = 0;

/**
 * 获取 WBI 签名密钥
 */
async function getWbiKeys() {
  // 缓存 1 小时
  if (cachedWbiKeys && Date.now() < wbiKeysExpireTime) {
    return cachedWbiKeys;
  }

  try {
    const response = await axios.get('https://api.bilibili.com/x/web-interface/nav', {
      headers: BILI_HEADERS,
      timeout: 10000
    });

    const data = response.data;
    if (data.code === 0 && data.data?.wbi_img) {
      const imgUrl = data.data.wbi_img.img_url;
      const subUrl = data.data.wbi_img.sub_url;
      
      // 提取 key
      const imgKey = imgUrl.split('/').pop().split('.')[0];
      const subKey = subUrl.split('/').pop().split('.')[0];
      
      cachedWbiKeys = { imgKey, subKey };
      wbiKeysExpireTime = Date.now() + 3600 * 1000; // 1小时
      
      console.log('[WBI] 密钥已更新');
      return cachedWbiKeys;
    }
  } catch (error) {
    console.error('[WBI] 获取密钥失败:', error.message);
  }
  
  return cachedWbiKeys;
}

/**
 * 生成 WBI 签名
 */
function encodeWbi(params, imgKey, subKey) {
  // 1. 拼接密钥
  const mixinKey = getMixinKey(imgKey + subKey);
  
  // 2. 添加时间戳
  const wts = Math.round(Date.now() / 1000);
  params.wts = wts;
  
  // 3. 按 key 排序并拼接
  const sortedParams = Object.keys(params).sort().map(key => {
    // 对值进行 URI 编码
    const value = encodeURIComponent(params[key]).replace(/[!'()*]/g, c => {
      return '%' + c.charCodeAt(0).toString(16).toUpperCase();
    });
    return `${key}=${value}`;
  }).join('&');
  
  // 4. 计算 w_rid
  const wbiSign = crypto.createHash('md5').update(sortedParams + mixinKey).digest('hex');
  
  return {
    ...params,
    w_rid: wbiSign
  };
}

function getMixinKey(orig) {
  let temp = '';
  for (let i = 0; i < 64; i++) {
    temp += orig[WBIMixinKeyEncTab[i]];
  }
  return temp.slice(0, 32);
}

// CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

app.use(express.json());

/**
 * 获取UP主信息 (带WBI签名)
 */
app.get('/api/up-info', async (req, res) => {
  const { mid } = req.query;
  if (!mid) return res.status(400).json({ code: -1, message: '缺少 mid 参数' });

  const cacheKey = `up_info_${mid}`;
  const cached = cache.get(cacheKey);
  if (cached) return res.json({ ...cached, fromCache: true });

  try {
    // 获取 WBI 密钥
    const wbiKeys = await getWbiKeys();
    if (!wbiKeys) throw new Error('无法获取 WBI 密钥');

    // 构建带签名的参数
    const params = encodeWbi({ mid }, wbiKeys.imgKey, wbiKeys.subKey);

    const response = await axios.get('https://api.bilibili.com/x/space/wbi/acc/info', {
      params,
      headers: BILI_HEADERS,
      timeout: 10000
    });

    const data = response.data;
    if (data.code === 0) {
      cache.set(cacheKey, data);
      console.log(`[Success] UP主 ${mid}: ${data.data?.name}`);
    }
    
    res.json(data);
  } catch (error) {
    console.error('[Error]', error.message);
    res.status(500).json({ code: -500, message: error.message });
  }
});

/**
 * 获取视频信息
 */
app.get('/api/video-info', async (req, res) => {
  const { bvid, aid } = req.query;
  if (!bvid && !aid) return res.status(400).json({ code: -1, message: '需要 bvid 或 aid' });

  const cacheKey = `video_${bvid || aid}`;
  const cached = cache.get(cacheKey);
  if (cached) return res.json({ ...cached, fromCache: true });

  try {
    const params = {};
    if (bvid) params.bvid = bvid;
    if (aid) params.aid = aid;

    const response = await axios.get('https://api.bilibili.com/x/web-interface/view', {
      params,
      headers: BILI_HEADERS,
      timeout: 10000
    });

    const data = response.data;
    if (data.code === 0) cache.set(cacheKey, data);
    res.json(data);
  } catch (error) {
    res.status(500).json({ code: -500, message: error.message });
  }
});

/**
 * 搜索视频 (需要WBI签名)
 */
app.get('/api/search', async (req, res) => {
  const { keyword, page = 1 } = req.query;
  if (!keyword) return res.status(400).json({ code: -1, message: '缺少 keyword' });

  try {
    const wbiKeys = await getWbiKeys();
    if (!wbiKeys) throw new Error('无法获取 WBI 密钥');

    const params = encodeWbi({
      search_type: 'video',
      keyword,
      page,
      pagesize: 20
    }, wbiKeys.imgKey, wbiKeys.subKey);

    const response = await axios.get('https://api.bilibili.com/x/web-interface/wbi/search/type', {
      params,
      headers: BILI_HEADERS,
      timeout: 10000
    });

    res.json(response.data);
  } catch (error) {
    res.status(500).json({ code: -500, message: error.message });
  }
});

// 健康检查
app.get('/health', async (req, res) => {
  const wbiKeys = await getWbiKeys().catch(() => null);
  res.json({
    status: 'ok',
    wbiReady: !!wbiKeys,
    cacheKeys: cache.keys().length,
    timestamp: new Date().toISOString()
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Server with WBI support running on port ${PORT}`);
  // 预加载 WBI 密钥
  getWbiKeys();
});
