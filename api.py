"""FastAPI接口服务"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import os
import time

# 导入后端功能
from utils import download_video
from exAudio import process_audio_split
from speech2text import load_whisper, run_analysis, load_doubao

# 加载豆包ASR引擎
load_doubao("5226088047", "enqjHJJKQYu8cprYR5sUUExsCYsHtoCJ")

# 创建FastAPI应用
app = FastAPI(
    title="Bili2Text API",
    description="B站视频转文字API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="."), name="static")

# 根路径返回index.html
@app.get("/")
async def root():
    return FileResponse("index.html")

# 请求模型
class VideoRequest(BaseModel):
    video_url: str

# 响应模型
class VideoResponse(BaseModel):
    success: bool
    text: str
    message: str
    processing_time: float

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Bili2Text API is running"}

# 视频转文字接口
@app.post("/api/convert", response_model=VideoResponse)
async def convert_video(request: VideoRequest):
    """将B站视频转换为文字"""
    start_time = time.time()
    
    try:
        # 提取BV号
        video_url = request.video_url
        if "BV" not in video_url:
            raise HTTPException(status_code=400, detail="视频链接必须包含BV号")
        
        # 提取BV号部分
        bv_start = video_url.find("BV")
        bv_end = video_url.find("?", bv_start) if "?" in video_url else len(video_url)
        bv_code = video_url[bv_start:bv_end]
        
        if len(bv_code) < 12:
            raise HTTPException(status_code=400, detail="BV号格式不正确")
        
        # 下载视频
        console_log(f"开始下载视频: {bv_code}")
        filename = download_video(bv_code[2:])
        
        if not filename:
            raise HTTPException(status_code=500, detail="视频下载失败")
        
        # 处理音频
        console_log(f"开始处理音频: {filename}")
        foldername = process_audio_split(filename, skip_split=True)
        
        if not foldername:
            raise HTTPException(status_code=500, detail="音频处理失败")
        
        # 加载模型并进行分析
        console_log(f"开始语音识别: {foldername}")
        
        # 默认使用豆包ASR
        result = run_analysis(foldername, prompt="以下是普通话的句子。这是一个关于投资的视频。", use_full_audio=True, use_doubao=True)
        
        if not result:
            raise HTTPException(status_code=500, detail="语音识别失败")
        
        processing_time = time.time() - start_time
        console_log(f"处理完成，耗时: {processing_time:.2f}秒")
        
        return VideoResponse(
            success=True,
            text=result,
            message="视频转换成功",
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        console_log(f"处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

# 控制台日志函数
def console_log(msg: str):
    """打印日志"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
