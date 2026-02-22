import os
import re
import subprocess
import glob  # 新增导入

# Bilibili 镜像站点配置（用于加速下载）
BILIBILI_MIRRORS = [
    "https://www.bilibili.com",  # 官方站点
    "https://b23.tv",  # 短链接站点
]

# 可选的代理配置（如果需要）
# 可以在这里设置 HTTP 代理，例如："http://127.0.0.1:7890"
HTTP_PROXY = os.environ.get("BILI_PROXY", "")

def ensure_folders_exist(output_dir):
    if not os.path.exists("bilibili_video"):
        os.makedirs("bilibili_video")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists("outputs"):
        os.makedirs("outputs")

def download_video(bv_number, use_proxy=None):
    """
    使用you-get下载B站视频，支持镜像站和代理加速。
    参数:
        bv_number: 字符串形式的BV号（不含"BV"前缀）或完整BV号
        use_proxy: HTTP代理地址，如 "http://127.0.0.1:7890"，None则使用环境变量BILI_PROXY
    返回:
        文件路径
    """
    if not bv_number.startswith("BV"):
        bv_number = "BV" + bv_number
    
    video_url = f"https://www.bilibili.com/video/{bv_number}"
    output_dir = f"bilibili_video/{bv_number}"  # 下载视频到 bilibili_video/{bv_number} 目录
    ensure_folders_exist(output_dir)
    
    # 确定代理设置
    proxy = use_proxy if use_proxy is not None else HTTP_PROXY
    
    print(f"使用you-get下载视频: {video_url}")
    if proxy:
        print(f"使用代理: {proxy}")
    
    # 构建you-get命令
    cmd = ["you-get", "-o", output_dir]
    if proxy:
        cmd.extend(["-x", proxy])
    cmd.append(video_url)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if result.returncode != 0:
            print("下载失败:", result.stderr)
            # 尝试不使用代理重试
            if proxy:
                print("尝试不使用代理重新下载...")
                cmd_no_proxy = ["you-get", "-o", output_dir, video_url]
                result = subprocess.run(cmd_no_proxy, capture_output=True, text=True, encoding="utf-8", errors="ignore")
                if result.returncode != 0:
                    print("重试下载失败:", result.stderr)
                    return ""
            else:
                return ""
        
        print(result.stdout)
        print(f"视频已成功下载到目录: {output_dir}")
        
        # 清理xml文件
        xml_files = glob.glob(os.path.join(output_dir, "*.xml"))
        for xml_file in xml_files:
            try:
                os.remove(xml_file)
                print(f"已删除弹幕文件: {xml_file}")
            except Exception as e:
                print(f"删除弹幕文件失败: {e}")
        
        # 检查下载的视频文件
        video_files = glob.glob(os.path.join(output_dir, "*.mp4"))
        if not video_files:
            # 尝试其他格式
            video_files = glob.glob(os.path.join(output_dir, "*.flv"))
        if not video_files:
            video_files = glob.glob(os.path.join(output_dir, "*.mkv"))
        
        if video_files:
            print(f"找到 {len(video_files)} 个视频文件")
            for vf in video_files:
                print(f"  - {os.path.basename(vf)}")
        else:
            print("警告: 未找到下载的视频文件")
            return ""
            
    except Exception as e:
        print("发生错误:", str(e))
        return ""
    
    return bv_number
