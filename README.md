<p align="center">
  <img src="light_logo2.png" alt="bili2text logo" width="400"/>
</p>


<p align="center">
    <img src="https://img.shields.io/github/stars/sunheyi6/billTotext" alt="GitHub stars"/>
    <img src="https://img.shields.io/github/license/sunheyi6/billTotext" alt="GitHub"/>
    <img src="https://img.shields.io/github/last-commit/sunheyi6/billTotext" alt="GitHub last commit"/>
</p>

# Bili2Text 📺

## 简介 🌟
Bili2Text 是一个用于将 Bilibili 视频转换为文本的工具🛠️。通过 Web 界面，用户可以轻松输入 B 站视频链接，系统会自动下载视频、提取音频并使用豆包 ASR 将语音转换为文本。

## 功能 🚀
- 🎥 **视频下载**：从 Bilibili 下载指定视频
- 🎵 **音频提取**：使用 FFmpeg 快速提取音频，支持硬件加速
- 💬 **语音转文字**：默认使用豆包 ASR 进行语音识别，更快更准确
- 🌐 **Web 界面**：响应式设计，支持一键复制转换结果
- 📱 **实时状态**：显示处理进度和错误提示

## 技术栈 🧰
- **后端**：Python + FastAPI
- **语音识别**：豆包 ASR (ByteDance)
- **音频处理**：FFmpeg (支持硬件加速)
- **前端**：HTML + Tailwind CSS + JavaScript
- **依赖管理**：pip

## 快速开始 📘

### 1. 克隆仓库
```bash
git clone https://github.com/sunheyi6/billTotext.git
cd billTotext
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置豆包 ASR
在 `api.py` 文件中，确保已正确配置豆包 ASR 的 API 凭证：
```python
# 加载豆包ASR引擎
load_doubao("5226088047", "enqjHJJKQYu8cprYR5sUUExsCYsHtoCJ")
```

### 4. 启动服务
```bash
python api.py
```

### 5. 使用 Web 界面
打开浏览器访问：
```
http://localhost:8000
```

1. 在输入框中粘贴 B 站视频链接
2. 点击「开始转换」按钮
3. 等待处理完成（视频下载和音频处理可能需要几分钟）
4. 查看转换结果并使用「复制」按钮复制文本

## 示例 📋

### 输入
```
https://www.bilibili.com/video/BV1Epf3BVExe/
```

### 输出
```
视频转换结果文本...
（可直接复制使用）
```

## 核心文件 📁
- **api.py** - FastAPI 后端服务，提供视频转文字 API
- **index.html** - 响应式前端界面
- **speech2text.py** - 语音识别核心逻辑（集成豆包 ASR）
- **exAudio.py** - 音频处理模块，支持硬件加速
- **doubao_asr.py** - 豆包 ASR 接口实现
- **utils.py** - 工具函数，包括视频下载

## 注意事项 ⚠️
- **网络环境**：需要稳定的网络连接以下载视频和调用豆包 ASR API
- **处理时间**：视频下载和音频处理时间取决于视频长度和网络速度
- **硬件要求**：建议使用支持硬件加速的设备以提高处理速度
- **版权合规**：请确保您有权利下载和转换的视频内容，尊重创作者的劳动成果

## 许可证 📄
本项目根据 MIT 许可证发布。

## 贡献 💡
如果你想为这个项目做出贡献，欢迎提交 Pull Request 或创建 Issue。

## 致谢 🙏
- 感谢 ByteDance 提供的豆包 ASR 服务
- 感谢 FFmpeg 团队提供的音频处理工具
- 感谢所有为开源社区做出贡献的开发者