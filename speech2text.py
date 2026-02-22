import os
import imageio_ffmpeg
import shutil
from faster_whisper import WhisperModel
from doubao_asr import DoubaoASREngine

# 获取 ffmpeg 路径
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# 将 ffmpeg 复制到当前目录，以便 Whisper 能找到
ffmpeg_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
ffprobe_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffprobe.exe")

# 如果本地没有 ffmpeg，则复制一份
if not os.path.exists(ffmpeg_local) and os.path.exists(FFMPEG_EXE):
    try:
        shutil.copy2(FFMPEG_EXE, ffmpeg_local)
        # 尝试复制 ffprobe（如果存在）
        ffprobe_src = FFMPEG_EXE.replace("ffmpeg", "ffprobe")
        if os.path.exists(ffprobe_src):
            shutil.copy2(ffprobe_src, ffprobe_local)
    except:
        pass

# 将当前目录添加到 PATH
os.environ["PATH"] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + os.environ.get("PATH", "")

# 如果复制失败，修改 Whisper 的 load_audio 函数来使用正确的 ffmpeg 路径
try:
    import whisper.audio
    original_load_audio = whisper.audio.load_audio
    
    def patched_load_audio(file: str, sr: int = whisper.audio.SAMPLE_RATE):
        """修改后的 load_audio，使用正确的 ffmpeg 路径"""
        from subprocess import CalledProcessError, run
        import numpy as np
        
        cmd = [
            FFMPEG_EXE,
            "-nostdin",
            "-threads", "0",
            "-i", file,
            "-f", "s16le",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            "-ar", str(sr),
            "-"
        ]
        try:
            out = run(cmd, capture_output=True, check=True).stdout
        except CalledProcessError as e:
            raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e
        
        return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
    
    # 替换原始函数
    whisper.audio.load_audio = patched_load_audio
except Exception as e:
    print(f"Warning: Could not patch whisper audio loader: {e}")

whisper_model = None
doubao_engine = None

def is_cuda_available():
    try:
        import torch
        return torch.cuda.is_available()
    except:
        return False

def load_whisper(model="tiny"):
    global whisper_model
    device = "cuda" if is_cuda_available() else "cpu"
    compute_type = "float16" if is_cuda_available() else "float32"
    whisper_model = WhisperModel(model, device=device, compute_type=compute_type)
    print(f"Whisper模型：{model} (faster-whisper)，设备：{device}，计算类型：{compute_type}")

def load_doubao(appid, access_key):
    """加载豆包ASR引擎
    
    Args:
        appid: 火山引擎应用ID
        access_key: 火山引擎Access Key
    """
    global doubao_engine
    doubao_engine = DoubaoASREngine(appid, access_key)
    print(f"豆包ASR引擎加载成功！AppID: {appid}")

def run_analysis(filename, model="tiny", prompt="以下是普通话的句子。", use_full_audio=False, use_doubao=False):
    global whisper_model, doubao_engine
    # 创建outputs文件夹
    os.makedirs("outputs", exist_ok=True)
    print("正在转换文本...")

    if use_doubao:
        # 使用豆包ASR引擎
        if doubao_engine is None:
            raise ValueError("豆包ASR引擎未加载，请先调用load_doubao函数加载引擎")
        
        # 直接处理完整音频文件
        audio_path = f"audio/conv/{filename}.mp3"
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"完整音频文件不存在: {audio_path}")
        
        print(f"正在使用豆包ASR处理完整音频文件: {audio_path}")
        text = doubao_engine.recognize_audio_file(audio_path)
        print("豆包ASR识别结果:")
        print(text)
        
        with open(f"outputs/{filename}_doubao.txt", "w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
        
        return text
    else:
        # 使用Whisper模型
        if whisper_model is None:
            load_whisper(model)
        
        print("正在加载Whisper模型...")
        print("加载Whisper模型成功！")

        if use_full_audio:
            # 直接处理完整音频文件
            audio_path = f"audio/conv/{filename}.mp3"
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"完整音频文件不存在: {audio_path}")
            
            print(f"正在处理完整音频文件: {audio_path}")
            segments, info = whisper_model.transcribe(audio_path, initial_prompt=prompt, language="zh")
            text = ""
            for segment in segments:
                text += segment.text
            print(text)
            
            with open(f"outputs/{filename}_full.txt", "w", encoding="utf-8") as f:
                f.write(text)
                f.write("\n")
            
            return text
        else:
            # 处理分割后的音频文件
            audio_list = os.listdir(f"audio/slice/{filename}")
            # 添加排序逻辑
            audio_files = sorted(
                audio_list,
                key=lambda x: int(os.path.splitext(x)[0])  # 按文件名数字排序
            )

            i = 1
            full_text = []
            for fn in audio_files:
                print(f"正在转换第{i}/{len(audio_files)}个音频... {fn}")
                # 识别音频
                segments, info = whisper_model.transcribe(f"audio/slice/{filename}/{fn}", initial_prompt=prompt, language="zh")
                segment_text = ""
                for segment in segments:
                    segment_text += segment.text
                print(segment_text)
                full_text.append(segment_text)

                with open(f"outputs/{filename}.txt", "a", encoding="utf-8") as f:
                    f.write(segment_text)
                    f.write("\n")
                i += 1
            
            return "\n".join(full_text)
