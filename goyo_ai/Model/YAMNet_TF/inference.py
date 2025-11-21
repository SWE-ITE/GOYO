import tensorflow as tf
import numpy as np
import os
from typing import List, Dict
import librosa

from layers import YAMNetLayer

MODEL_PATH = 'checkpoints/best_model.keras'
TOTAL_CHUNKS = 5
AUDIO_LENGTH_SAMPLES = 15600
SAMPLE_RATE = 16000

SENSOR_CONFIGS: Dict[int, str] = {
    1: "Air_conditioner",
    2: "Hair_dryer",
    3: "Microwave",
    4: "Refrigerator_Hum",
    5: "Vacuum"
}

CLASS_NAMES = [
    'Air_conditioner',
    'Hair_dryer',
    'Microwave',
    'Others', 
    'Refrigerator_Hum', 
    'Vacuum',
]

# 나중에 실시간 연결되면 지워도 될 함수
def preprocess_audio_file(file_path):
    try:
        wav_data, _ = librosa.load(file_path, sr=SAMPLE_RATE, mono=True)

        if len(wav_data) < AUDIO_LENGTH_SAMPLES:
            # 짧으면 뒤에 0으로 패딩
            wav_data = np.pad(wav_data, (0, AUDIO_LENGTH_SAMPLES - len(wav_data)))
        else:
            # 길면 앞에서부터 15600개만 자름 (실시간 청크 시뮬레이션)
            wav_data = wav_data[:AUDIO_LENGTH_SAMPLES]
            
        return wav_data.astype(np.float32)
        
    except Exception as e:
        print(f"파일 로드 실패 ({file_path}): {e}")
        # 실패 시 0으로 채운 더미 반환
        return np.zeros(AUDIO_LENGTH_SAMPLES, dtype=np.float32)


def load_trained_model(model_path: str) -> tf.keras.Model:
    if not os.path.exists(model_path):
        print(f"error: 모델 파일을 찾을 수 없습니다: {model_path}")
        return None
    
    try:
        model = tf.keras.models.load_model(
            model_path,
            custom_objects={'YAMNetLayer': YAMNetLayer}  # custom_objects에 임포트한 YAMNetLayer 클래스를 전달
        )
        print("모델 로드 완료.")
        return model
    except Exception as e:
        print(f"모델 로드 실패: {e}")
        return None
    

def run_final_filtering(
    model: tf.keras.Model,
    mic_id: int, 
    buffer_of_chunks: List[np.ndarray]
) -> None:

    expected_class = SENSOR_CONFIGS.get(mic_id)

    if len(buffer_of_chunks) != TOTAL_CHUNKS:
        print(f"청크 개수 오류")
        return

    input_batch = np.array(buffer_of_chunks) # 분류 모델 작동 (5개 청크를 배치로 묶어 1번 실행)
    prob_outputs = model.predict(input_batch, verbose=0) # 결과 shape: (5, 10)
    
    predicted_indices = np.argmax(prob_outputs, axis=1) # 확률을 클래스 인덱스로 변환

    match_count = 0
    
    print(f"\n--- [Mic {mic_id}: {expected_class}] 추론 결과 ---")
    
    for i, idx in enumerate(predicted_indices):
        pred_class = CLASS_NAMES[idx]
        is_match = (pred_class == expected_class)
        
        if is_match:
            match_count += 1
            
        print(f"   Chunk {i+1}: {pred_class} [{'O' if is_match else 'X'}]")

    if (match_count/TOTAL_CHUNKS)>=0.8:
        print(f"ANC 작동 신호 전송 ({match_count}/{TOTAL_CHUNKS} 일치)")
    else:
        print(f"신호 무시 ({match_count}/{TOTAL_CHUNKS} 일치)")

#예시실행코드 - 수정필요
if __name__ == "__main__":
   model = load_trained_model(MODEL_PATH) 
   if model:
        TEST_DIR = "/Users/kimtaerim/Desktop/GOYO/goyo_ai/Dataset/Test_data" 
        
        TEST_FILENAMES = [
            "cleaner2.m4a",
            "cleaner2.m4a",
            "cleaner2.m4a",
            "cleaner2.m4a",
            "miaow_16k.wav"
        ]
        
        print(f"\n📂 파일 로드 중... ({TEST_DIR})")
        real_audio_buffer = []
        
        for fname in TEST_FILENAMES:
            full_path = os.path.join(TEST_DIR, fname)
            audio_chunk = preprocess_audio_file(full_path)
            real_audio_buffer.append(audio_chunk)

        TARGET_MIC_ID = 5 
        print(f"📡 Mic {TARGET_MIC_ID} 시뮬레이션 시작...")
        run_final_filtering(model, mic_id=TARGET_MIC_ID, buffer_of_chunks=real_audio_buffer)