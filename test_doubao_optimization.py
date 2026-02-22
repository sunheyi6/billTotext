"""测试优化后的豆包ASR识别功能"""

import os
import re
import sys
import time
from utils import download_video
from exAudio import process_audio_split
import speech2text


def test_doubao_optimization():
    """测试豆包ASR优化效果"""
    print("=" * 80)
    print("测试优化后的豆包ASR识别功能")
    print("=" * 80)
    
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
    
    total_start_time = time.time()
    
    try:
        # 1. 下载视频
        print("\n1. 正在下载视频...")
        download_start = time.time()
        file_identifier = download_video(bv_number)
        download_time = time.time() - download_start
        print(f"视频下载成功: {file_identifier}")
        print(f"下载耗时: {download_time:.2f}秒")
        
        # 2. 提取和处理音频
        print("\n2. 正在处理音频...")
        audio_start = time.time()
        folder_name = process_audio_split(file_identifier, skip_split=True)  # 跳过分割，直接使用完整音频
        audio_time = time.time() - audio_start
        print(f"音频处理成功: {folder_name}")
        print(f"音频处理耗时: {audio_time:.2f}秒")
        
        # 3. 加载豆包ASR引擎
        print("\n3. 正在加载豆包ASR引擎...")
        asr_start = time.time()
        # 使用用户提供的豆包API配置
        speech2text.load_doubao("5226088047", "enqjHJJKQYu8cprYR5sUUExsCYsHtoCJ")
        asr_load_time = time.time() - asr_start
        print(f"豆包ASR引擎加载成功！")
        print(f"引擎加载耗时: {asr_load_time:.2f}秒")
        
        # 4. 转换文本
        print("\n4. 正在使用豆包ASR转换文本...")
        transcribe_start = time.time()
        result = speech2text.run_analysis(folder_name, 
            prompt="以下是普通话的句子。这是一个关于投资的视频。",
            use_full_audio=True,
            use_doubao=True)
        transcribe_time = time.time() - transcribe_start
        print("文本转换成功！")
        print(f"识别耗时: {transcribe_time:.2f}秒")
        
        # 5. 显示结果
        print("\n5. 转换结果预览:")
        preview = result[:500] + "..." if len(result) > 500 else result
        print(preview)
        
        # 6. 检查输出文件
        output_file = f"outputs/{folder_name}_doubao.txt"
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / 1024
            print(f"\n6. 输出文件已生成:")
            print(f"文件路径: {output_file}")
            print(f"文件大小: {file_size:.2f} KB")
        else:
            print(f"\n6. 错误: 输出文件未生成")
        
        # 7. 总耗时统计
        total_time = time.time() - total_start_time
        print(f"\n7. 总耗时统计:")
        print(f"总耗时: {total_time:.2f}秒")
        print(f"- 下载: {download_time:.2f}秒 ({download_time/total_time*100:.1f}%)")
        print(f"- 音频处理: {audio_time:.2f}秒 ({audio_time/total_time*100:.1f}%)")
        print(f"- 引擎加载: {asr_load_time:.2f}秒 ({asr_load_time/total_time*100:.1f}%)")
        print(f"- 语音识别: {transcribe_time:.2f}秒 ({transcribe_time/total_time*100:.1f}%)")
        
        print("\n测试完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n测试失败！")
        print("=" * 80)


if __name__ == "__main__":
    test_doubao_optimization()
