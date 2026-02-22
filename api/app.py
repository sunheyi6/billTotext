"""FastAPI接口服务"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# 挂载静态文件服务
app.mount("/static", StaticFiles(directory="../"), name="static")

# 根路径返回index.html
@app.get("/")
async def root():
    return FileResponse("../index.html")

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Bili2Text API is running"}
