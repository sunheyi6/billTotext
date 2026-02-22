import os
import re
import sys
import threading
from utils import download_video
from exAudio import process_audio_split
import speech2text

def test_conversion():
    print("=== Bili2Text 测试脚本 ===")
    
    # 测试视频链接
    video_link = "https://www.bilibili.com/video/BV1Epf3BVExe/?spm_id_from=333.1387.upload.video_card.click&vd_source=4c59531496f49b45d7abd87d9ea8318f"
    print(f"测试视频链接: {video_link}")
    
    # 提取BV号
    pattern = r'BV[A-Za-z0-9]+'
    matches = re.findall(pattern, video_link)
    if not matches:
        print("无效的视频链接！")
        return
    bv_number = matches[0]
    print(f"提取的BV号: {bv_number}")
    
    try:
        # 1. 下载视频
        print("\n1. 正在下载视频...")
        file_identifier = download_video(bv_number)
        print(f"视频下载成功: {file_identifier}")
        
        # 2. 提取和处理音频
        print("\n2. 正在处理音频...")
        folder_name = process_audio_split(file_identifier, skip_split=True)  # 跳过分割，直接使用完整音频
        print(f"音频处理成功: {folder_name}")
        
        # 3. 加载Whisper模型
        print("\n3. 正在加载Whisper模型...")
        speech2text.load_whisper(model="tiny")
        print("Whisper模型加载成功！")
        
        # 4. 转换文本
        print("\n4. 正在转换文本...")
        result = speech2text.run_analysis(folder_name, 
            prompt="以下是普通话的句子。这是一个关于投资的视频。",
            use_full_audio=True)
        print("文本转换成功！")
        
        # 5. 显示结果
        print("\n5. 转换结果预览:")
        preview = result[:500] + "..." if len(result) > 500 else result
        print(preview)
        
        # 6. 检查输出文件
        output_file = f"outputs/{folder_name}_full.txt"
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / 1024
            print(f"\n6. 输出文件已生成:")
            print(f"文件路径: {output_file}")
            print(f"文件大小: {file_size:.2f} KB")
            print("测试成功！")
        else:
            print(f"\n6. 错误: 输出文件未生成")
            print("测试失败！")
            
    except Exception as e:
        print(f"\n测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_conversion()
