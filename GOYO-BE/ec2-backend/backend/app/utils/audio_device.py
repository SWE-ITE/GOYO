import pyaudio
import numpy as np
from typing import List, Dict, Optional

class AudioDeviceManager:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.sample_rate = 44100
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
    
    def list_usb_microphones(self) -> List[Dict]:
        '''USB 마이크 목록 조회'''
        devices = []
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            
            if info['maxInputChannels'] > 0:
                devices.append({
                    'device_id': f"USB_MIC_{i}",
                    'device_name': info['name'],
                    'device_type': 'microphone_unknown',  
                    'connection_type': 'usb',
                    'index': i,
                    'channels': info['maxInputChannels'],
                    'sample_rate': int(info['defaultSampleRate'])
                })
        return devices
    
    def open_input_stream(self, device_index: int):
        '''입력 스트림 열기'''
        stream = self.p.open(
            format=self.format,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.chunk_size
        )
        return stream
    
    def read_audio_chunk(self, stream) -> np.ndarray:
        '''오디오 청크 읽기'''
        data = stream.read(self.chunk_size, exception_on_overflow=False)
        audio_array = np.frombuffer(data, dtype=np.int16)
        return audio_array
    
    def calculate_audio_level(self, audio_data: np.ndarray) -> float:
        '''오디오 레벨 계산 (RMS)'''
        rms = np.sqrt(np.mean(audio_data**2))
        db = 20 * np.log10(rms + 1e-6)  
        return float(db)
    
    def close(self):
        '''PyAudio 종료'''
        self.p.terminate()

audio_manager = AudioDeviceManager()