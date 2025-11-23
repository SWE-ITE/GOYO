import numpy as np
import librosa

def add_noise(audio_data, noise_factor=0.005): #add noise
    noise = np.random.randn(len(audio_data))
    augmented_data = audio_data + noise_factor * noise
    augmented_data = augmented_data.astype(type(audio_data[0]))
    return augmented_data

def pitch_shift(audio_data, sample_rate, n_steps=4): #피치 무작위로
    return librosa.effects.pitch_shift(y=audio_data, sr=sample_rate, n_steps=n_steps)
    
def mask_time(audio_data, t_width_max=1000):
    augmented_data = audio_data.copy()
    num_masks = np.random.randint(1,5)
    for _ in range(num_masks):
        t = np.random.randint(0, augmented_data.shape[0])
        t_width = np.random.randint(1, t_width_max + 1)

        # 오디오 길이를 넘지 않도록 끝부분을 보정
        if t + t_width > augmented_data.shape[0]:
            t_width = augmented_data.shape[0] - t
        augmented_data[t:t+t_width] = 0
    return augmented_data

def mask_freq(wav_data, f_width_max=10):
    stft = librosa.stft(wav_data) # 오디오를 스펙트로그램으로 변환
    f_count_max = stft.shape[0] # 총 주파수 밴드 수
    num_masks = np.random.randint(1, 5) # 마스크 개수 1 ~ 5 랜덤
    
    for _ in range(num_masks):
        f = np.random.randint(0, f_count_max)
        f_width = np.random.randint(1, f_width_max + 1)
    
        if f + f_width > stft.shape[0]: #stft.shape[0]을 넘지 않도록 보정
            f_width = stft.shape[0] - f
        stft[f:f+f_width, :] = 0 # 해당 주파수 밴드를 0으로(무음) 만듦
    return librosa.istft(stft)