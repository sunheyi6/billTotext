const BiliAPI = require('../../utils/bilibili.js');

Page({
  data: {
    mid: '',
    loading: false,
    upInfo: null,
    error: null,
    serverStatus: null
  },

  onLoad() {
    // 检查服务状态
    this.checkServerStatus();
  },

  // 输入UP主ID
  onMidInput(e) {
    this.setData({ mid: e.detail.value });
  },

  // 检查服务状态
  async checkServerStatus() {
    try {
      const res = await BiliAPI.healthCheck();
      this.setData({ serverStatus: res.status === 'ok' ? '正常' : '异常' });
    } catch (e) {
      this.setData({ serverStatus: '连接失败' });
    }
  },

  // 查询UP主信息
  async queryUpInfo() {
    const mid = this.data.mid.trim();
    
    if (!mid) {
      wx.showToast({ title: '请输入UP主ID', icon: 'none' });
      return;
    }

    if (!/^\d+$/.test(mid)) {
      wx.showToast({ title: 'ID必须是数字', icon: 'none' });
      return;
    }

    this.setData({ loading: true, error: null, upInfo: null });
    wx.showLoading({ title: '查询中...' });

    try {
      const res = await BiliAPI.getUpInfo(mid);
      
      if (res.code === 0 && res.data) {
        this.setData({ upInfo: res.data });
        wx.showToast({ title: '查询成功', icon: 'success' });
      } else {
        throw new Error(res.message || '未知错误');
      }
    } catch (err) {
      console.error('查询失败:', err);
      this.setData({ error: err.message || '查询失败' });
      wx.showToast({ title: err.message || '查询失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
      wx.hideLoading();
    }
  },

  // 复制信息
  copyInfo() {
    const info = this.data.upInfo;
    if (!info) return;
    
    const text = `UP主：${info.name}\n签名：${info.sign}\n粉丝：${this.formatNumber(info.follower)}`;
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' })
    });
  },

  // 格式化数字
  formatNumber(num) {
    if (!num) return '0';
    if (num >= 10000) {
      return (num / 10000).toFixed(1) + '万';
    }
    return num.toString();
  },

  // 清除缓存
  clearCache() {
    BiliAPI.clearCache();
    wx.showToast({ title: '缓存已清除', icon: 'success' });
  }
});
