"""
YAMNet TFLite 추론 모듈 - 라즈베리파이용 (통합 모델)
audio_client.py와 통합 가능 (bytes 입력 지원)
48kHz → 16kHz 리샘플링 지원
YAMNet + Classifier 통합 모델 사용 (원스텝 추론)
"""
import numpy as np
import os
from scipy import signal

# 라즈베리 파이용 tflite
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite

# ================= 설정 =================
CLASSIFIER_PATH = "models/classifier.tflite"  # 통합 모델 (YAMNet + Classifier)

SAMPLE_RATE = 16000
INPUT_SIZE = 15600  # YAMNet 입력 샘플 개수

CLASS_NAMES = [
    'Air_conditioner',      # 0
    'Hair_dryer',           # 1
    'Microwave',            # 2
    'Others',               # 3
    'Refrigerator_Hum',     # 4
    'Vacuum'                # 5
]


# ================= 리샘플링 함수 =================
def resample_to_16k(audio_bytes, source_rate=48000):
    """
    48kHz (또는 다른 샘플레이트) → 16kHz 리샘플링

    Args:
        audio_bytes: int16 PCM bytes
        source_rate: 원본 샘플레이트 (기본 48000)

    Returns:
        int16 PCM bytes (16kHz)
    """
    if source_rate == 16000:
        return audio_bytes  # 이미 16kHz면 그대로 반환

    # bytes → numpy int16
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

    # 리샘플 (source_rate → 16000)
    num_samples_16k = int(len(audio_np) * 16000 / source_rate)
    audio_16k = signal.resample(audio_np, num_samples_16k)

    # int16로 변환
    audio_16k = np.clip(audio_16k, -32768, 32767).astype(np.int16)

    return audio_16k.tobytes()


# ================= 추론 클래스 (audio_client.py용) =================
class YAMNetClassifier:
    """
    YAMNet + 분류기 통합 TFLite 모델
    audio_client.py에서 사용 가능 (bytes 입력 지원)
    """

    def __init__(self, classifier_path=CLASSIFIER_PATH):
        """통합 모델 로드 (YAMNet + Classifier 원스텝)"""
        if not os.path.exists(classifier_path):
            raise FileNotFoundError(f"❌ 통합 모델 없음: {classifier_path}")

        self.classifier = tflite.Interpreter(model_path=classifier_path)
        self.classifier.allocate_tensors()

        # 입력/출력 텐서 인덱스
        self.input_details = self.classifier.get_input_details()
        self.output_details = self.classifier.get_output_details()

        self.input_index = self.input_details[0]['index']
        self.output_index = self.output_details[0]['index']

        print(f"✅ 통합 모델 로드: {classifier_path}")
        print(f"   입력 shape: {self.input_details[0]['shape']}")
        print(f"   출력 shape: {self.output_details[0]['shape']}")

    def predict_from_bytes(self, audio_bytes, source_rate=48000):
        """
        실시간 캡처된 bytes를 추론 (audio_client.py용)
        자동으로 16kHz로 리샘플링 지원
        통합 모델로 원스텝 추론

        Args:
            audio_bytes: int16 PCM bytes
            source_rate: 원본 샘플레이트 (기본 48000)

        Returns:
            predicted_class: 0~5 (클래스 인덱스)
            confidence: 0.0~1.0 (신뢰도)
        """
        # 48kHz → 16kHz 리샘플링 (필요시)
        if source_rate != 16000:
            audio_bytes = resample_to_16k(audio_bytes, source_rate)

        # bytes → numpy int16
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

        # 15600 샘플만 사용
        audio_np = audio_np[:INPUT_SIZE]

        # 부족한 샘플 패딩
        if len(audio_np) < INPUT_SIZE:
            audio_np = np.pad(audio_np, (0, INPUT_SIZE - len(audio_np)), 'constant')

        # float32 정규화 [-1.0, 1.0]
        audio_float = audio_np.astype(np.float32) / 32768.0

        # 입력 shape: (1, 15600)
        input_tensor = audio_float[np.newaxis, ...]

        # 통합 모델 추론 (YAMNet + Classifier 원스텝)
        self.classifier.set_tensor(self.input_index, input_tensor)
        self.classifier.invoke()
        probs = self.classifier.get_tensor(self.output_index)[0]  # (6,)

        # 결과
        predicted_class = int(np.argmax(probs))
        confidence = float(probs[predicted_class])

        return predicted_class, confidence

    def classify_buffer(self, buffer_of_chunks, consistency_threshold=4, source_rate=48000, target_class=None):
        """
        5개 청크 버퍼 분류 (일관성 체크)

        Args:
            buffer_of_chunks: 5개 오디오 청크 리스트 (bytes)
            consistency_threshold: 일관성 임계값 (기본 4/5 = 80%)
            source_rate: 원본 샘플레이트 (기본 48000)

        Returns:
            - "APPLIANCE_DETECTED": 가전 소음 확인
            - None: 외부 소음 또는 일관성 부족
        """
        if len(buffer_of_chunks) != 5:
            print(f"⚠️ 청크 개수 오류: {len(buffer_of_chunks)} (5개 필요)")
            return None

        # 5개 청크 각각 추론
        predictions = []
        confidences = []

        for i, chunk in enumerate(buffer_of_chunks):
            pred_class, confidence = self.predict_from_bytes(chunk, source_rate)
            predictions.append(pred_class)
            confidences.append(confidence)
            print(f"  Chunk {i+1}: {CLASS_NAMES[pred_class]} ({confidence*100:.1f}%)")

        # 가장 많이 예측된 클래스
        unique, counts = np.unique(predictions, return_counts=True)
        most_common_class = int(unique[np.argmax(counts)])
        most_common_count = int(np.max(counts))

        print(f"📊 결과: {CLASS_NAMES[most_common_class]} ({most_common_count}/5 일치)")

        # "Others" 클래스면 무시
        if most_common_class == 3:
            print("❌ 외부 소음 (Others) - 무시")
            return None

        # 일관성 체크 (기본 80% = 4/5)
        if most_common_count >= consistency_threshold:
            # target_class가 지정된 경우, 해당 클래스만 감지
            if target_class is not None and most_common_class != target_class:
                print(f"❌ 다른 가전 소음 ({CLASS_NAMES[most_common_class]}) - 무시 (target: {CLASS_NAMES[target_class] if target_class < len(CLASS_NAMES) else target_class})")
                return None
            print(f"✅ 가전 소음 확인: {CLASS_NAMES[most_common_class]}")
            return "APPLIANCE_DETECTED"
        else:
            print(f"❌ 일관성 부족 ({most_common_count}/5) - 무시")
            return None


# ================= 로컬 테스트용 (선택사항) =================
def load_wav_16k_mono(filename):
    """
    테스트용: wav 파일 읽기 (파이썬 기본 wave 모듈 사용)
    실제 라즈베리파이에서는 사용 안 함
    """
    import wave

    try:
        with wave.open(filename, 'rb') as wf:
            if wf.getframerate() != 16000:
                print(f"⚠️ {filename}은 16kHz가 아닙니다.")
                return np.zeros(INPUT_SIZE, dtype=np.float32)

            if wf.getnchannels() != 1:
                print(f"⚠️ {filename}은 Mono가 아닙니다.")
                return np.zeros(INPUT_SIZE, dtype=np.float32)

            frames = wf.readframes(wf.getnframes())
            audio_data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            if len(audio_data) < INPUT_SIZE:
                audio_data = np.pad(audio_data, (0, INPUT_SIZE - len(audio_data)))
            else:
                audio_data = audio_data[:INPUT_SIZE]

            return audio_data

    except Exception as e:
        print(f"❌ 파일 읽기 실패: {e}")
        return np.zeros(INPUT_SIZE, dtype=np.float32)


if __name__ == "__main__":
    print("📡 YAMNet 통합 모델 테스트...")

    try:
        # 통합 모델 로드
        classifier = YAMNetClassifier()

        # 테스트 1: 더미 bytes로 테스트 (48kHz)
        print("\n🧪 테스트 1: 더미 오디오 48kHz (bytes) → 16kHz 리샘플링")
        dummy_audio_48k = np.random.randint(-32768, 32767, 48000, dtype=np.int16).tobytes()
        pred_class, confidence = classifier.predict_from_bytes(dummy_audio_48k, source_rate=48000)
        print(f"   결과: {CLASS_NAMES[pred_class]} ({confidence*100:.1f}%)")

        # 테스트 2: 5개 청크 버퍼
        print("\n🧪 테스트 2: 5개 청크 버퍼 (48kHz)")
        buffer = [dummy_audio_48k] * 5
        result = classifier.classify_buffer(buffer, source_rate=48000)
        print(f"   최종 결과: {result}")

        # 테스트 3: wav 파일 (있으면)
        test_file = "test.wav"
        if os.path.exists(test_file):
            print(f"\n🧪 테스트 3: {test_file}")
            audio_float = load_wav_16k_mono(test_file)
            # float32를 int16 bytes로 변환
            audio_bytes = (audio_float * 32768).astype(np.int16).tobytes()
            pred_class, confidence = classifier.predict_from_bytes(audio_bytes, source_rate=16000)
            print(f"   결과: {CLASS_NAMES[pred_class]} ({confidence*100:.1f}%)")

        print("\n✅ 모든 테스트 완료!")
        print("📝 통합 모델 (YAMNet + Classifier) 정상 작동")

    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
