import numpy as np
import librosa
import torch
from torch.utils.data import Dataset
from augment_utils import add_noise, pitch_shift, mask_time, mask_freq

class SoundDataGeneratorPyTorch(Dataset):
    def __init__(self, file_paths, labels, target_length, sample_rate, augment=False):
        self.file_paths = file_paths
        self.labels = labels
        self.target_length = target_length
        self.sample_rate = sample_rate
        self.augment = augment

    def __len__(self): #데이터 총 몇개인지
        return len(self.file_paths)

    def __getitem__(self, index):
        file_path = self.file_paths[index]
        label = self.labels[index]
        
        try:
            wav_data, _ = librosa.load(file_path, sr=self.sample_rate, mono=True)
            wav_data, _ = librosa.effects.trim(wav_data, top_db=30) #30db 이하의, 보통 시작과 끝 부분을 자른다.
            
            if len(wav_data) < self.target_length: #15,600보다 적으면 부족한 만큼 0으로 채움
                wav_data = np.pad(wav_data, (0, self.target_length - len(wav_data)))
            else: #15,600보다 같거나 크면, 그 사이의 랜덤한 부분에서 15,600만큼 가져옴
                max_start_index = len(wav_data) - self.target_length
                start_index = np.random.randint(0, max_start_index) if max_start_index > 0 else 0
                wav_data = wav_data[start_index : start_index + self.target_length]
            
            #Augmentation
            if self.augment:
                if np.random.rand() > 0.5:
                    wav_data = add_noise(wav_data, noise_factor=np.random.uniform(0.001, 0.005))
                if np.random.rand() > 0.3:
                    wav_data = pitch_shift(wav_data, self.sample_rate, n_steps=np.random.randint(-2, 3))
                if np.random.rand() > 0.3:
                    wav_data = mask_time(wav_data)
                if  np.random.rand() > 0.7: #학습 너무 오래걸리면 얘는 지워야 할 듯
                    wav_data = mask_freq(wav_data)

            # Augmentation을 겪고 혹시라도 길이가 바뀔 수 있기 때문에 조정.
            if len(wav_data) < self.target_length:
                wav_data = np.pad(wav_data, (0, self.target_length - len(wav_data)))
            elif len(wav_data) > self.target_length:
                wav_data = wav_data[:self.target_length]
            
            # 5. 텐서 변환
            audio_tensor = torch.tensor(wav_data, dtype=torch.float32)
            label_tensor = torch.tensor(label, dtype=torch.long)
            
            return audio_tensor, label_tensor

        except Exception as e:
            print(f"error : {e}")
            return torch.zeros(self.target_length, dtype=torch.float32), torch.tensor(0, dtype=torch.long)