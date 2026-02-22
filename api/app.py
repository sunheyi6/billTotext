"""FastAPI接口服务"""

# Vercel deployment support
from fastapi import FastAPI
from fastapi.responses import FileResponse

# 创建FastAPI应用
app = FastAPI(
    title="Bili2Text API",
    description="B站视频转文字API",
    version="1.0.0"
)

# 根路径返回index.html
@app.get("/")
async def root():
    return FileResponse("../index.html")

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Bili2Text API is running"}
