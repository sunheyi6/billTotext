"""豆包语音识别引擎 - 支持完整音频文件识别

参考Vocept项目的实现
"""

import json
import struct
import uuid
import time
import threading
import traceback
import hmac
import hashlib
import base64
from typing import Optional, List, Dict, Any, Callable
from enum import IntEnum
import websocket
import os
import numpy as np
import requests
from subprocess import CalledProcessError, run

# 控制台日志函数
def console_log(msg: str, level: str = "INFO"):
    """打印日志到控制台"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] {msg}", flush=True)


class MessageType(IntEnum):
    """消息类型"""
    FULL_CLIENT_REQUEST = 0b0001
    AUDIO_ONLY_REQUEST = 0b0010
    FULL_SERVER_RESPONSE = 0b1001
    ERROR_RESPONSE = 0b1111


class MessageFlags(IntEnum):
    """消息标志"""
    NONE = 0b0000
    SEQUENCE_NUMBER = 0b0001
    LAST_PACKET = 0b0010
    SEQUENCE_NUMBER_LAST = 0b0011


class SerializationMethod(IntEnum):
    """序列化方法"""
    NONE = 0b0000
    JSON = 0b0001


class CompressionType(IntEnum):
    """压缩类型"""
    NONE = 0b0000
    GZIP = 0b0001


class DoubaoASREngine:
    """豆包语音识别引擎 - 支持完整音频文件识别
    """
    
    # WebSocket URL
    WS_URL = "wss://openspeech.bytedance.com/api/v2/asr"
    
    # HTTP API URL (大模型录音文件极速版)
    HTTP_API_FLASH = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    
    # 默认资源 ID
    DEFAULT_RESOURCE_ID = "volcengine_streaming_common"
    
    def __init__(self, appid: str, access_key: str):
        """初始化豆包 ASR 引擎"""
        self._appid = appid
        self._access_key = access_key
        self._cluster_id = self.DEFAULT_RESOURCE_ID
        
        # WebSocket 连接
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        
        # 事件
        self._stop_event = threading.Event()
        self._connected_event = threading.Event()
        self._ready_event = threading.Event()
        
        # 识别结果
        self._current_result = ""
        self._final_result = None
        
        # 序列号
        self._sequence_number = 0
        
        # 音频参数
        self.sample_rate = 16000
        self.language = "zh"
    
    def _build_header(
        self,
        msg_type: MessageType,
        flags: MessageFlags = MessageFlags.NONE,
        serialization: SerializationMethod = SerializationMethod.JSON,
        compression: CompressionType = CompressionType.NONE
    ) -> bytes:
        """构建协议头（4字节）"""
        byte0 = (0b0001 << 4) | 0b0001
        byte1 = (msg_type << 4) | flags
        byte2 = (serialization << 4) | compression
        byte3 = 0x00
        return bytes([byte0, byte1, byte2, byte3])
    
    def _build_full_client_request(self) -> bytes:
        """构建 full client request"""
        reqid = str(uuid.uuid4())
        
        payload = {
            "app": {
                "appid": self._appid,
                "token": self._access_key,
                "cluster": self._cluster_id,
            },
            "user": {
                "uid": f"bili2text_{int(time.time())}",
            },
            "audio": {
                "format": "raw",
                "codec": "raw",
                "rate": self.sample_rate,
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "reqid": reqid,
                "sequence": 1,
                "nbest": 1,
                "workflow": "audio_in,resample,partition,vad,fe,decode,itn,nlu_punctuate",
                "show_utterances": False,
                "result_type": "full",
            }
        }
        
        payload_json = json.dumps(payload)
        import gzip
        payload_bytes = gzip.compress(payload_json.encode('utf-8'))
        payload_size = len(payload_bytes)
        
        header = self._build_header(
            MessageType.FULL_CLIENT_REQUEST,
            MessageFlags.NONE,
            SerializationMethod.JSON,
            CompressionType.GZIP
        )
        
        message = header + struct.pack('>I', payload_size) + payload_bytes
        return message
    
    def _build_audio_request(self, audio_data: bytes, is_last: bool = False) -> bytes:
        """构建 audio only request"""
        header = self._build_header(
            MessageType.AUDIO_ONLY_REQUEST,
            MessageFlags.NONE,
            SerializationMethod.NONE,
            CompressionType.NONE
        )
        
        payload_size = len(audio_data)
        message = header + struct.pack('>I', payload_size) + audio_data
        return message
    
    def _parse_server_response(self, data: bytes) -> Optional[Dict]:
        """解析服务器响应"""
        if len(data) < 4:
            return None
        
        header = data[:4]
        msg_type = (header[1] >> 4) & 0x0F
        header_size = header[0] & 0x0F
        extension_header_len = (header_size - 1) * 4
        payload_start = 4 + extension_header_len
        
        if len(data) < payload_start:
            return None
        
        payload = data[payload_start:]
        payload_msg = None
        
        if msg_type == MessageType.FULL_SERVER_RESPONSE:
            if len(payload) < 4:
                return None
            payload_size = int.from_bytes(payload[:4], "big", signed=True)
            if len(payload) < 4 + payload_size:
                return None
            payload_msg = payload[4:4 + payload_size]
        elif msg_type == MessageType.ERROR_RESPONSE:
            if len(payload) < 8:
                return None
            code = int.from_bytes(payload[:4], "big", signed=False)
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            if len(payload) < 8 + payload_size:
                return None
            payload_msg = payload[8:8 + payload_size]
        
        if payload_msg is None:
            return None
        
        compression = header[2] & 0x0F
        if compression == CompressionType.GZIP:
            import gzip
            try:
                payload_msg = gzip.decompress(payload_msg)
            except Exception as e:
                print(f"解压响应失败: {e}")
                return None
        
        serialization = (header[2] >> 4) & 0x0F
        if serialization == SerializationMethod.JSON:
            try:
                data_dict = json.loads(payload_msg.decode('utf-8'))
                if not isinstance(data_dict, dict):
                    return {"error": True, "message": f"响应格式错误: {data_dict}", "data": data_dict}
                
                if msg_type == MessageType.ERROR_RESPONSE:
                    return {"error": True, "message": data_dict.get('message', 'Server error'), "data": data_dict}
                
                code = data_dict.get('code', 0)
                message = data_dict.get('message', '')
                
                if code != 1000:
                    return {"error": True, "message": message, "data": data_dict}
                
                return data_dict
            except json.JSONDecodeError as e:
                print(f"解析 JSON 响应失败: {e}")
                return None
        
        return None
    
    def _on_ws_open(self, ws):
        """WebSocket 连接打开回调"""
        console_log("[DoubaoASR] WebSocket 连接已打开")
        self._connected_event.set()
        
        try:
            request = self._build_full_client_request()
            ws.send(request, opcode=websocket.ABNF.OPCODE_BINARY)
            console_log("[DoubaoASR] full client request 已发送")
        except Exception as e:
            console_log(f"[DoubaoASR] 发送配置请求失败: {e}", "ERROR")
    
    def _on_ws_message(self, ws, message):
        """WebSocket 消息回调"""
        if isinstance(message, str):
            console_log(f"[DoubaoASR] 文本消息: {message}")
            return
        
        response = self._parse_server_response(message)
        if response is None:
            return
        
        if not isinstance(response, dict):
            return
        
        if response.get("error"):
            error_message = response.get("message", "Unknown error")
            console_log(f"[DoubaoASR] 服务器错误: {error_message}", "ERROR")
            return
        
        code = response.get("code", 0)
        if code == 1000:
            self._ready_event.set()
        
        if "result" in response:
            result_data = response["result"]
            
            if isinstance(result_data, list) and len(result_data) > 0:
                result_item = result_data[0]
            elif isinstance(result_data, dict):
                result_item = result_data
            else:
                return
            
            if not isinstance(result_item, dict):
                return
            
            text = ""
            if "text" in result_item:
                text = result_item["text"]
            elif "utterances" in result_item and isinstance(result_item["utterances"], list) and len(result_item["utterances"]) > 0:
                utterance = result_item["utterances"][0]
                if isinstance(utterance, dict):
                    text = utterance.get("text", "")
            
            is_final = result_item.get("definite", False) or result_item.get("is_final", False)
            
            if is_final:
                console_log(f"[DoubaoASR] 识别完成，结果长度: {len(text)} 字符")
                self._final_result = text
            else:
                # 不打印中间结果，只更新当前结果
                self._current_result = text
    
    def _on_ws_error(self, ws, error):
        """WebSocket 错误回调"""
        try:
            if isinstance(error, list):
                error_msg = f"List error: {error}"
            elif isinstance(error, dict):
                error_msg = f"Dict error: {error}"
            else:
                error_msg = str(error)
        except Exception as e:
            error_msg = f"Unknown error: {e}"
        
        console_log(f"[DoubaoASR] WebSocket 错误: {error_msg}", "ERROR")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket 关闭回调"""
        console_log(f"[DoubaoASR] WebSocket 已关闭: {close_status_code} - {close_msg}")
    

    
    def _send_last_packet(self):
        """发送最后一包"""
        if self._ws and self._ws.sock and self._ws.sock.connected:
            try:
                request = self._build_audio_request(b'', is_last=True)
                self._ws.send(request, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                console_log(f"[DoubaoASR] 发送结束包失败: {e}", "ERROR")
    
    def _upload_audio_to_server(self, audio_path: str) -> str:
        """上传音频文件到临时服务器获取URL
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            音频文件的URL
        """
        # 这里需要实现音频文件上传逻辑
        # 暂时返回本地文件路径（实际使用时需要上传到可访问的服务器）
        console_log(f"[DoubaoASR] 音频文件路径: {audio_path}")
        return audio_path
    
    def _load_audio_file(self, audio_path: str) -> bytes:
        """快速加载音频文件并转换为PCM格式，使用FFmpeg硬件加速"""
        console_log(f"[DoubaoASR] 快速加载音频文件: {audio_path}")
        
        # 检查文件是否存在
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 构建FFmpeg命令，尝试使用硬件加速
        cmd = [
            "ffmpeg",
            "-hwaccel", "auto",  # 自动检测硬件加速
            "-i", audio_path,
            "-vn",  # 不处理视频
            "-acodec", "pcm_s16le",  # 16位PCM
            "-ar", str(self.sample_rate),  # 采样率
            "-ac", "1",  # 单声道
            "-f", "s16le",  # 输出格式
            "-threads", "0",  # 自动使用所有核心
            "-loglevel", "quiet",  # 静默输出
            "-"
        ]
        
        try:
            start_time = time.time()
            out = run(cmd, capture_output=True, check=True).stdout
            elapsed = time.time() - start_time
            console_log(f"[DoubaoASR] 音频转换成功，大小: {len(out)} bytes, 耗时: {elapsed:.2f}秒")
            return out
        except CalledProcessError as e:
            console_log(f"[DoubaoASR] 音频转换失败: {e.stderr.decode()}", "ERROR")
            # 回退到不使用硬件加速的版本
            console_log("[DoubaoASR] 回退到不使用硬件加速的版本")
            fallback_cmd = [
                "ffmpeg",
                "-i", audio_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", str(self.sample_rate),
                "-ac", "1",
                "-f", "s16le",
                "-threads", "0",
                "-loglevel", "quiet",
                "-"
            ]
            try:
                out = run(fallback_cmd, capture_output=True, check=True).stdout
                console_log(f"[DoubaoASR] 回退版本转换成功，大小: {len(out)} bytes")
                return out
            except CalledProcessError as e2:
                console_log(f"[DoubaoASR] 回退版本也失败: {e2.stderr.decode()}", "ERROR")
                raise
    
    def recognize_audio_file(self, audio_path: str) -> str:
        """识别完整音频文件
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别结果文本
        """
        console_log(f"[DoubaoASR] 开始识别音频文件: {audio_path}")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        try:
            # 重置状态
            self._stop_event.clear()
            self._connected_event.clear()
            self._ready_event.clear()
            self._current_result = ""
            self._final_result = None
            self._sequence_number = 0
            

            
            # 构建请求头
            headers = [
                f'Authorization: Bearer; {self._access_key}',
            ]
            
            # 创建 WebSocket 连接
            console_log(f"[DoubaoASR] 连接到: {self.WS_URL}")
            self._ws = websocket.WebSocketApp(
                self.WS_URL,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
                header=headers
            )
            
            # 启动 WebSocket 线程
            self._ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
            self._ws_thread.start()
            
            # 等待连接就绪
            console_log("[DoubaoASR] 等待连接就绪 (最多5秒)...")
            if not self._connected_event.wait(timeout=5.0):
                raise RuntimeError("WebSocket 连接超时")
            console_log("[DoubaoASR] WebSocket 连接成功")
            
            # 等待服务器就绪
            console_log("[DoubaoASR] 等待服务器就绪 (最多10秒)...")
            if not self._ready_event.wait(timeout=10.0):
                console_log("[DoubaoASR] 警告: 服务器未明确返回就绪信号，但继续", "WARN")
            else:
                console_log("[DoubaoASR] 服务器就绪")
            
            # 加载音频文件
            audio_data = self._load_audio_file(audio_path)
            
            # 一次性发送完整音频数据
            console_log(f"[DoubaoASR] 开始发送完整音频数据，大小: {len(audio_data)} bytes")
            
            # 分块发送（每个块不超过30秒音频）
            # 16kHz * 2 bytes/sample * 30s = 960000 bytes
            chunk_size = 900000  # 约28秒音频 per chunk
            total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
            
            console_log(f"[DoubaoASR] 将音频分为 {total_chunks} 个块，每个块最多 {chunk_size} bytes")
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                if chunk:
                    if self._ws and self._ws.sock and self._ws.sock.connected:
                        request = self._build_audio_request(chunk, is_last=(i + chunk_size >= len(audio_data)))
                        self._ws.send(request, opcode=websocket.ABNF.OPCODE_BINARY)
                        
                        current_chunk = i // chunk_size + 1
                        if current_chunk % 5 == 0 or current_chunk == total_chunks:
                            console_log(f"[DoubaoASR] 已发送 {current_chunk}/{total_chunks} 个数据块")
                        
                        # 短暂延迟，避免发送过快
                        time.sleep(0.1)
            
            # 发送结束标记
            self._send_last_packet()
            
            # 等待识别完成
            console_log("[DoubaoASR] 等待识别完成 (最多60秒)...")
            wait_time = 0
            max_wait = 60.0
            
            while wait_time < max_wait:
                if self._final_result is not None:
                    console_log(f"[DoubaoASR] 收到最终结果，等待时间: {wait_time:.1f}s")
                    break
                time.sleep(1.0)
                wait_time += 1.0
            
            # 如果没有收到最终结果，使用当前结果
            if self._final_result is None:
                if self._current_result:
                    console_log(f"[DoubaoASR] 使用当前结果作为最终结果: {self._current_result[:50]}...")
                    self._final_result = self._current_result
                else:
                    console_log("[DoubaoASR] 警告: 没有识别结果", "WARN")
                    self._final_result = ""
            
            console_log(f"[DoubaoASR] 识别完成，结果长度: {len(self._final_result)} 字符")
            return self._final_result
            
        except Exception as e:
            console_log(f"[DoubaoASR] 识别过程中出错: {e}", "ERROR")
            traceback.print_exc()
            raise
        finally:
            # 清理资源
            self._stop_event.set()
            
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
            
            if self._ws_thread and self._ws_thread.is_alive():
                self._ws_thread.join(timeout=1.0)
    
    def recognize_audio_file_http(self, audio_path: str) -> str:
        """使用HTTP API识别完整音频文件（大模型录音文件极速版）
        
        直接上传音频文件，一次请求即返回识别结果，无需轮询
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别结果文本
        """
        console_log(f"[DoubaoASR] 使用大模型极速版API识别音频文件: {audio_path}")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        try:
            # 读取音频文件并转换为base64
            console_log("[DoubaoASR] 读取音频文件...")
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            # 将音频数据转换为base64
            base64_audio = base64.b64encode(audio_data).decode('utf-8')
            console_log(f"[DoubaoASR] 音频文件大小: {len(audio_data)} bytes, Base64长度: {len(base64_audio)}")
            
            # 构建请求头
            headers = {
                "X-Api-App-Key": self._appid,
                "X-Api-Access-Key": self._access_key,
                "X-Api-Resource-Id": "volc.bigasr.auc_turbo",
                "X-Api-Request-Id": str(uuid.uuid4()),
                "X-Api-Sequence": "-1",
                "Content-Type": "application/json"
            }
            
            # 构建请求体
            payload = {
                "user": {
                    "uid": self._appid
                },
                "audio": {
                    "data": base64_audio
                },
                "request": {
                    "model_name": "bigmodel"
                }
            }
            
            console_log(f"[DoubaoASR] 发送请求到: {self.HTTP_API_FLASH}")
            
            # 发送请求
            response = requests.post(
                self.HTTP_API_FLASH,
                json=payload,
                headers=headers,
                timeout=120  # 设置超时时间为120秒
            )
            
            # 检查响应头
            status_code = response.headers.get('X-Api-Status-Code')
            status_message = response.headers.get('X-Api-Message')
            log_id = response.headers.get('X-Tt-Logid')
            
            console_log(f"[DoubaoASR] 响应状态码: {status_code}, 消息: {status_message}")
            
            if status_code == '20000000':
                # 识别成功
                result = response.json()
                text = result.get("result", {}).get("text", "")
                console_log(f"[DoubaoASR] 识别完成，结果长度: {len(text)} 字符")
                return text
            else:
                # 识别失败
                error_msg = f"API返回错误: {status_code} - {status_message}"
                console_log(f"[DoubaoASR] {error_msg}", "ERROR")
                raise Exception(error_msg)
            
        except Exception as e:
            console_log(f"[DoubaoASR] HTTP API识别过程中出错: {e}", "ERROR")
            traceback.print_exc()
            # 回退到WebSocket方式
            console_log("[DoubaoASR] 回退到WebSocket方式")
            return self.recognize_audio_file_ws(audio_path)
    
    def recognize_audio_file_ws(self, audio_path: str) -> str:
        """使用WebSocket识别完整音频文件
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别结果文本
        """
        console_log(f"[DoubaoASR] 使用WebSocket开始识别音频文件: {audio_path}")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        try:
            # 重置状态
            self._stop_event.clear()
            self._connected_event.clear()
            self._ready_event.clear()
            self._current_result = ""
            self._final_result = None
            self._sequence_number = 0
            
            # 构建请求头
            headers = [
                f'Authorization: Bearer; {self._access_key}',
            ]
            
            # 创建 WebSocket 连接
            console_log(f"[DoubaoASR] 连接到: {self.WS_URL}")
            self._ws = websocket.WebSocketApp(
                self.WS_URL,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
                header=headers
            )
            
            # 启动 WebSocket 线程
            self._ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
            self._ws_thread.start()
            
            # 等待连接就绪
            console_log("[DoubaoASR] 等待连接就绪 (最多5秒)...")
            if not self._connected_event.wait(timeout=5.0):
                raise RuntimeError("WebSocket 连接超时")
            console_log("[DoubaoASR] WebSocket 连接成功")
            
            # 等待服务器就绪
            console_log("[DoubaoASR] 等待服务器就绪 (最多10秒)...")
            if not self._ready_event.wait(timeout=10.0):
                console_log("[DoubaoASR] 警告: 服务器未明确返回就绪信号，但继续", "WARN")
            else:
                console_log("[DoubaoASR] 服务器就绪")
            
            # 加载音频文件
            audio_data = self._load_audio_file(audio_path)
            
            # 一次性发送完整音频数据
            console_log(f"[DoubaoASR] 开始发送完整音频数据，大小: {len(audio_data)} bytes")
            
            # 分块发送（每个块不超过30秒音频）
            # 16kHz * 2 bytes/sample * 30s = 960000 bytes
            chunk_size = 900000  # 约28秒音频 per chunk
            total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size
            
            console_log(f"[DoubaoASR] 将音频分为 {total_chunks} 个块，每个块最多 {chunk_size} bytes")
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                if chunk:
                    if self._ws and self._ws.sock and self._ws.sock.connected:
                        request = self._build_audio_request(chunk, is_last=(i + chunk_size >= len(audio_data)))
                        self._ws.send(request, opcode=websocket.ABNF.OPCODE_BINARY)
                        
                        current_chunk = i // chunk_size + 1
                        if current_chunk % 5 == 0 or current_chunk == total_chunks:
                            console_log(f"[DoubaoASR] 已发送 {current_chunk}/{total_chunks} 个数据块")
                        
                        # 短暂延迟，避免发送过快
                        time.sleep(0.1)
            
            # 发送结束标记
            self._send_last_packet()
            
            # 等待识别完成
            console_log("[DoubaoASR] 等待识别完成 (最多60秒)...")
            wait_time = 0
            max_wait = 60.0
            
            while wait_time < max_wait:
                if self._final_result is not None:
                    console_log(f"[DoubaoASR] 收到最终结果，等待时间: {wait_time:.1f}s")
                    break
                time.sleep(1.0)
                wait_time += 1.0
            
            # 如果没有收到最终结果，使用当前结果
            if self._final_result is None:
                if self._current_result:
                    console_log(f"[DoubaoASR] 使用当前结果作为最终结果: {self._current_result[:50]}...")
                    self._final_result = self._current_result
                else:
                    console_log("[DoubaoASR] 警告: 没有识别结果", "WARN")
                    self._final_result = ""
            
            console_log(f"[DoubaoASR] 识别完成，结果长度: {len(self._final_result)} 字符")
            return self._final_result
            
        except Exception as e:
            console_log(f"[DoubaoASR] WebSocket识别过程中出错: {e}", "ERROR")
            traceback.print_exc()
            raise
        finally:
            # 清理资源
            self._stop_event.set()
            
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
            
            if self._ws_thread and self._ws_thread.is_alive():
                self._ws_thread.join(timeout=1.0)
    
    def recognize_audio_file(self, audio_path: str) -> str:
        """识别完整音频文件
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别结果文本
        """
        try:
            # 优先使用HTTP API（极速版）
            return self.recognize_audio_file_http(audio_path)
        except Exception as e:
            console_log(f"[DoubaoASR] HTTP API失败，回退到WebSocket: {e}")
            return self.recognize_audio_file_ws(audio_path)
    
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self._appid and self._access_key)
