"""FastAPI接口服务"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os

app = FastAPI()

# 根路径返回简单的JSON响应，验证API是否正常工作
@app.get("/")
async def root():
    try:
        # 测试当前目录
        current_dir = os.getcwd()
        # 测试文件存在性
        index_path = os.path.join(os.path.dirname(current_dir), "index.html")
        index_exists = os.path.exists(index_path)
        
        return JSONResponse({
            "status": "ok",
            "message": "Bili2Text API is running",
            "current_dir": current_dir,
            "index_path": index_path,
            "index_exists": index_exists
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Bili2Text API is running"}
