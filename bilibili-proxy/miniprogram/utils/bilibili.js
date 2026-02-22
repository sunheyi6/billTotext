/**
 * 小程序 Bilibili API 封装
 * 统一错误处理、缓存、重试机制
 */

// API 基础地址 - 修改为你的服务器地址
const API_BASE = 'https://your-domain.com';  // 生产环境
// const API_BASE = 'http://localhost:3000'; // 开发环境

// 本地缓存管理
const CacheManager = {
  // 获取缓存
  get(key) {
    try {
      const data = wx.getStorageSync(`bili_cache_${key}`);
      if (!data) return null;
      
      // 检查是否过期 (默认5分钟)
      if (Date.now() - data.timestamp > 5 * 60 * 1000) {
        wx.removeStorageSync(`bili_cache_${key}`);
        return null;
      }
      return data.value;
    } catch (e) {
      return null;
    }
  },
  
  // 设置缓存
  set(key, value, ttl = 5 * 60) {
    try {
      wx.setStorageSync(`bili_cache_${key}`, {
        value,
        timestamp: Date.now()
      });
    } catch (e) {
      console.error('Cache set error:', e);
    }
  },
  
  // 清除缓存
  clear() {
    const keys = wx.getStorageInfoSync().keys;
    keys.forEach(key => {
      if (key.startsWith('bili_cache_')) {
        wx.removeStorageSync(key);
      }
    });
  }
};

// 请求封装
const request = (options) => {
  return new Promise((resolve, reject) => {
    const { url, data, method = 'GET', cacheKey, cacheTTL, retry = 1 } = options;
    
    // 检查缓存
    if (cacheKey) {
      const cached = CacheManager.get(cacheKey);
      if (cached) {
        console.log('[Cache Hit]', cacheKey);
        resolve(cached);
        return;
      }
    }
    
    const doRequest = (attempt) => {
      wx.request({
        url: `${API_BASE}${url}`,
        method,
        data,
        header: {
          'Content-Type': 'application/json'
        },
        timeout: 15000,
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            const data = res.data;
            
            // 业务逻辑成功
            if (data.code === 0) {
              // 写入缓存
              if (cacheKey) {
                CacheManager.set(cacheKey, data, cacheTTL);
              }
              resolve(data);
            } else {
              reject({
                code: data.code,
                message: data.message || '请求失败',
                data
              });
            }
          } else {
            // HTTP 错误
            if (attempt < retry) {
              setTimeout(() => doRequest(attempt + 1), 1000 * attempt);
            } else {
              reject({
                code: res.statusCode,
                message: `HTTP 错误: ${res.statusCode}`
              });
            }
          }
        },
        fail: (err) => {
          if (attempt < retry) {
            setTimeout(() => doRequest(attempt + 1), 1000 * attempt);
          } else {
            reject({
              code: -1,
              message: err.errMsg || '网络请求失败'
            });
          }
        }
      });
    };
    
    doRequest(1);
  });
};

/**
 * Bilibili API 封装
 */
const BiliAPI = {
  /**
   * 获取UP主信息
   * @param {string|number} mid - UP主ID
   * @param {boolean} useCache - 是否使用缓存
   */
  getUpInfo(mid, useCache = true) {
    return request({
      url: '/api/up-info',
      data: { mid },
      cacheKey: useCache ? `up_${mid}` : null,
      retry: 2
    });
  },
  
  /**
   * 批量获取UP主信息
   * @param {Array} mids - UP主ID数组
   */
  getUpInfoBatch(mids) {
    return request({
      url: '/api/up-info-batch',
      method: 'POST',
      data: { mids },
      retry: 1
    });
  },
  
  /**
   * 获取视频信息
   * @param {string} bvid - BV号
   * @param {number} aid - AV号 (可选)
   * @param {boolean} useCache - 是否使用缓存
   */
  getVideoInfo(bvid, aid, useCache = true) {
    const params = {};
    if (bvid) params.bvid = bvid;
    if (aid) params.aid = aid;
    
    return request({
      url: '/api/video-info',
      data: params,
      cacheKey: useCache && bvid ? `video_${bvid}` : null,
      retry: 2
    });
  },
  
  /**
   * 健康检查
   */
  healthCheck() {
    return request({
      url: '/health',
      cacheKey: null,
      retry: 1
    }).catch(() => ({ status: 'error' }));
  },
  
  // 清除缓存
  clearCache() {
    CacheManager.clear();
  }
};

module.exports = BiliAPI;
