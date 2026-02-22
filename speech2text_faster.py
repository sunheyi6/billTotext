import os
import time
import imageio_ffmpeg

# 设置 ffmpeg 路径
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] = os.path.dirname(FFMPEG_PATH) + os.pathsep + os.environ.get("PATH", "")

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("错误: 请先安装 faster-whisper: pip install faster-whisper")
    raise

whisper_model = None

def load_whisper(model_size="small"):
    """加载 faster-whisper 模型
    
    模型大小选项:
    - tiny: 39M, 最快但准确度较低
    - base: 74M
    - small: 244M, 中文推荐
    - medium: 769M
    - large-v1/v2/v3: 1.5G, 最准确但最慢
    """
    global whisper_model
    
    # 使用 Chinese Whisper 模型 (针对中文优化的 large-v3)
    if model_size == "chinese":
        model_path = "BELLE-2/Belle-whisper-large-v3-zh"
    else:
        model_path = model_size
    
    print(f"正在加载 faster-whisper 模型: {model_path}")
    
    # 检测是否有 CUDA
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
    except:
        device = "cpu"
        compute_type = "int8"
    
    print(f"使用设备: {device}, 计算类型: {compute_type}")
    
    whisper_model = WhisperModel(
        model_path,
        device=device,
        compute_type=compute_type,
        download_root="models"
    )
    print(f"模型加载完成！")
    return whisper_model

def transcribe_audio(audio_path, prompt="以下是普通话的句子。"):
    """转录音频文件"""
    global whisper_model
    
    if whisper_model is None:
        load_whisper("small")
    
    segments, info = whisper_model.transcribe(
        audio_path,
        language="zh",
        initial_prompt=prompt,
        vad_filter=True,  # 使用 VAD 过滤静音
        vad_parameters=dict(min_silence_duration_ms=500)
    )
    
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text)
    
    return "".join(text_parts)

def run_analysis(filename, prompt="以下是普通话的句子。"):
    """批量转录音频切片"""
    import glob
    
    print("=" * 50)
    print("使用 faster-whisper 进行语音转文字")
    print("=" * 50)
    
    # 加载模型
    if whisper_model is None:
        load_whisper("small")
    
    # 获取音频文件列表
    audio_dir = f"audio/slice/{filename}"
    audio_files = sorted(
        [f for f in os.listdir(audio_dir) if f.endswith('.mp3')],
        key=lambda x: int(os.path.splitext(x)[0])
    )
    
    total = len(audio_files)
    print(f"\n找到 {total} 个音频片段")
    print("开始转录...\n")
    
    # 创建输出目录
    os.makedirs("outputs", exist_ok=True)
    output_file = f"outputs/{filename}_faster.txt"
    
    # 清空或创建文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"转录时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"使用模型: faster-whisper (small)\n")
        f.write("=" * 50 + "\n\n")
    
    full_text = []
    start_time = time.time()
    
    for i, audio_file in enumerate(audio_files, 1):
        audio_path = os.path.join(audio_dir, audio_file)
        
        print(f"[{i}/{total}] 转录中: {audio_file}")
        segment_start = time.time()
        
        try:
            text = transcribe_audio(audio_path, prompt)
            segment_time = time.time() - segment_start
            
            print(f"    完成! 耗时: {segment_time:.1f}s")
            print(f"    内容: {text[:80]}..." if len(text) > 80 else f"    内容: {text}")
            
            full_text.append(text)
            
            # 实时写入文件
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"[{i}/{total}] {text}\n")
                
        except Exception as e:
            print(f"    错误: {e}")
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"[{i}/{total}] [转录失败: {e}]\n")
    
    total_time = time.time() - start_time
    
    # 写入总结
    with open(output_file, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 50 + "\n")
        f.write(f"转录完成! 总耗时: {total_time:.1f}秒\n")
        f.write(f"平均每段: {total_time/total:.1f}秒\n\n")
        f.write("完整文本:\n")
        f.write("\n".join(full_text))
    
    print("\n" + "=" * 50)
    print(f"转录完成! 总耗时: {total_time:.1f}秒")
    print(f"结果保存: {output_file}")
    print("=" * 50)
    
    return "\n".join(full_text)

if __name__ == "__main__":
    # 测试
    folder_name = "20260207065918"
    result = run_analysis(folder_name)
    print("\n转录结果预览:")
    print(result[:500])
