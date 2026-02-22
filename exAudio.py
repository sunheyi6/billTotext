from moviepy import VideoFileClip, AudioFileClip
import os
import time
import subprocess

def check_video_integrity(file_path):
    """使用 FFmpeg 验证视频文件完整性"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
            stderr=subprocess.PIPE,
            text=True
        )
        if result.stderr:
            print(f"视频文件可能损坏: {file_path}")
            print(f"FFmpeg 错误信息: {result.stderr}")
            return False
        return True
    except FileNotFoundError:
        print("警告: 未找到ffmpeg，跳过视频完整性检查")
        return True

def convert_flv_to_mp3(name, target_name=None, folder='bilibili_video'):
    """快速提取音频，使用FFmpeg硬件加速"""
    # 先尝试直接拼接 .mp4
    input_path = f'{folder}/{name}.mp4'
    if not os.path.exists(input_path):
        # 如果不存在，尝试在文件夹下查找视频文件
        dir_path = f'{folder}/{name}'
        if os.path.isdir(dir_path):
            for file in os.listdir(dir_path):
                if file.endswith(('.mp4', '.flv', '.mkv', '.avi')):
                    input_path = os.path.join(dir_path, file)
                    break
            else:
                raise FileNotFoundError(f"目录下未找到视频文件: {dir_path}")
        else:
            raise FileNotFoundError(f"视频文件不存在: {input_path}")
    if not check_video_integrity(input_path):
        raise ValueError(f"视频文件损坏: {input_path}")
    # 提取视频中的音频并保存为 MP3 到 audio/conv 目录
    try:
        os.makedirs("audio/conv", exist_ok=True)
        output_name = target_name if target_name else name
        output_path = f"audio/conv/{output_name}.mp3"
        
        # 使用FFmpeg直接提取音频，启用硬件加速
        import subprocess
        start_time = time.time()
        
        cmd = [
            "ffmpeg",
            "-hwaccel", "auto",  # 自动检测硬件加速
            "-i", input_path,
            "-vn",  # 不处理视频
            "-acodec", "libmp3lame",  # MP3编码器
            "-q:a", "2",  # 音质设置，2是高质量
            "-threads", "0",  # 自动使用所有核心
            "-loglevel", "quiet",  # 静默输出
            output_path
        ]
        
        subprocess.run(cmd, check=True)
        elapsed = time.time() - start_time
        print(f"音频提取成功，耗时: {elapsed:.2f}秒")
        print(f"音频保存到: {output_path}")
    except Exception as e:
        print(f"提取音频时出错: {str(e)}")
        print("警告: 音频提取失败，可能无法进行语音转文字")

def split_mp3(filename, folder_name, slice_length=45, target_folder="audio/slice"):
    """使用moviepy分割音频文件
    slice_length: 分割长度（秒），默认45秒
    """
    try:
        audio = AudioFileClip(filename)
        duration = audio.duration
        total_slices = int((duration + slice_length - 1) // slice_length)
        target_dir = os.path.join(target_folder, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        
        for i in range(total_slices):
            start = i * slice_length
            end = min(start + slice_length, duration)
            slice_audio = audio.subclipped(start, end)
            slice_path = os.path.join(target_dir, f"{i+1}.mp3")
            slice_audio.write_audiofile(slice_path, logger=None)
            print(f"Slice {i+1}/{total_slices} saved: {slice_path}")
        
        audio.close()
    except Exception as e:
        print(f"分割音频时出错: {str(e)}")
        raise

def process_audio_split(name, skip_split=False):
    # 生成唯一文件夹名，并依次调用转换和分割函数
    folder_name = time.strftime('%Y%m%d%H%M%S')
    convert_flv_to_mp3(name, target_name=folder_name)
    conv_path = f"audio/conv/{folder_name}.mp3"
    if not os.path.exists(conv_path):
        raise FileNotFoundError(f"转换后的音频文件不存在: {conv_path}")
    
    if not skip_split:
        split_mp3(conv_path, folder_name)
    else:
        print("跳过音频分割，直接处理完整音频")
    
    return folder_name

