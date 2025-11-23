import numpy as np
import librosa
import math
from tensorflow.keras.utils import Sequence  # Keras에서 Sequence를 임포트
from augment_utils import add_noise, pitch_shift, mask_time, mask_freq

#Keras를 위한 실시간 오디오 데이터 제너레이터
class SoundDataGenerator(Sequence):
    def __init__(self, file_paths, labels, batch_size, target_length, 
                 sample_rate, class_names, augment=False):
        self.file_paths = file_paths
        self.labels = labels
        self.batch_size = batch_size
        self.target_length = target_length
        self.sample_rate = sample_rate
        self.class_names = class_names
        self.augment = augment      #True면 훈련용, False면 검증용
        self.n_classes = len(class_names)
        self.on_epoch_end()         #한번 섞어줌

    def __len__(self):
        """한 에폭당 배치 갯수"""
        return math.ceil(len(self.file_paths) / self.batch_size)

    def __getitem__(self, index): #Keras가 model.fit에서 'index'번째 배치를 요청할 때 호출되는 함수
        start_idx = index * self.batch_size
        end_idx = (index + 1) * self.batch_size

        # 리스트에서 [0:32] (0~31번) 파일 경로와 라벨 32개를 꺼냄
        batch_paths = self.file_paths[start_idx:end_idx]
        batch_labels = self.labels[start_idx:end_idx]
        
        # 데이터를 담을 빈 Numpy 배열 생성
        X_batch = np.zeros((len(batch_paths), self.target_length), dtype=np.float32)  # (batch_size, 15600)
        y_batch = np.array(batch_labels, dtype=np.int32) # (batch_size,)
        
        #augmentation
        for i, (file_path, label) in enumerate(zip(batch_paths, batch_labels)):
            try:
                wav_data, _ = librosa.load(file_path, sr=self.sample_rate, mono=True)
                wav_data, _ = librosa.effects.trim(wav_data, top_db=30) #시작과 끝의 '무음' 구간을 자동으로 잘라냄
                
                if len(wav_data) < self.target_length:
                    wav_data = np.pad(wav_data, (0, self.target_length - len(wav_data)))
                else:
                    max_start_index = len(wav_data) - self.target_length
                    start_index = np.random.randint(0, max_start_index) if max_start_index > 0 else 0
                    wav_data = wav_data[start_index : start_index + self.target_length]
                
                    
                #augment
                if self.augment:
                    # 현재 데이터의 클래스 이름 확인
                    current_class = self.class_names[label]

                    # [그룹 A] 타겟 가전제품 (Microwave, Vacuum 등)
                    # 데이터가 적어서 복사본이 많음 -> 과적합 방지 위해 '강한 증강' 필수
                    if current_class != 'Others':
                        if np.random.rand() > 0.5:
                            wav_data = add_noise(wav_data, noise_factor=np.random.uniform(0.001, 0.005))
                        if np.random.rand() > 0.3:
                            wav_data = pitch_shift(wav_data, self.sample_rate, n_steps=np.random.randint(-2, 3))
                        if np.random.rand() > 0.3:
                            wav_data = mask_time(wav_data)
                        if np.random.rand() > 0.7:
                            wav_data = mask_freq(wav_data)
                
                    else:
                        # Others는 이미 데이터셋이 다양하기 때문에 약한 증강
                        if np.random.rand() > 0.8:
                            wav_data = add_noise(wav_data, noise_factor=np.random.uniform(0.001, 0.005))
                        if np.random.rand() > 0.8:
                            wav_data = pitch_shift(wav_data, self.sample_rate, n_steps=np.random.randint(-2, 3))
                        if np.random.rand() > 0.8:
                            wav_data = mask_time(wav_data)
                        if np.random.rand() > 0.8:
                            wav_data = mask_freq(wav_data)
                        
                if len(wav_data) < self.target_length: #15600보다 짧을 때 zero-padding
                    wav_data = np.pad(wav_data, (0, self.target_length - len(wav_data)))
                else:
                    max_start_index = len(wav_data) - self.target_length
                    if max_start_index > 0:
                        start_index = np.random.randint(0, max_start_index) 
                    else:
                        start_index = 0
                    wav_data = wav_data[start_index : start_index + self.target_length] #길이가 15600보다 길면 랜덤으로 중간 어느지점을 15600만큼 자름
                
                X_batch[i] = wav_data
                
            except Exception as e:
                print(f"error : - {e}")
        return X_batch, y_batch

    def on_epoch_end(self):# 매 에폭마다 데이터 섞어주기 위해서. + 파일 경로와 라벨을 '같은 순서로' 섞어야 함
        indices = np.arange(len(self.file_paths)) # train file갯수만큼 인덱스 리스트
        np.random.shuffle(indices)
        self.file_paths = [self.file_paths[i] for i in indices]
        self.labels = [self.labels[i] for i in indices]         #'파일 경로'와 '라벨' 리스트를 섞인 순서대로 재정렬