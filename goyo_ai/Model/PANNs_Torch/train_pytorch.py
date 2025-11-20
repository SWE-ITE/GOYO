import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
import os
import glob
from sklearn.model_selection import train_test_split
from sklearn.utils import class_weight
from tqdm import tqdm
from pathlib import Path

from dataset_PANNs import SoundDataGeneratorPyTorch
from model_PANNs import PANNs_Tuned_Model

SAMPLE_RATE = 16000
AUDIO_LENGTH_SAMPLES = 15600
DATASET_PATH = Path(__file__).resolve().parent.parent / 'Dataset' / 'Final_dataset'
CLASS_NAMES = [
    'Air_conditioner', 'Air_plane', 'Background', 'Car_horn', 
    'Children_playing', 'Clock_tick', 'Dog_bark', 'Drilling', 
    'Engine_idling', 'Fan', 'Hair_dryer', 'Jackhammer', 
    'Keyboard_typing', 'Rain', 'Refrigerator_Hum', 'Siren', 
    'Snoring', 'Train', 'Vacuum', 'Washing_machine'
]
NOISE_CLASSES = len(CLASS_NAMES)

script_dir = os.path.dirname(os.path.realpath(__file__))
PANN_WEIGHTS_PATH = os.path.join(
    script_dir, "..", "audioset_tagging_cnn", "Cnn14_16k_mAP=0.438.pth" # audioset_tagging_cnn다운로드 후 본인 경로 맞춰서 수정
)
if not os.path.exists(PANN_WEIGHTS_PATH):
        print(f"PANNs 가중치 파일을 찾을 수 없습니다. : {PANN_WEIGHTS_PATH}")
        PANN_WEIGHTS_PATH = None

# 경로 scan함수
def scan_dataset(dataset_path, class_names):
    file_paths = []
    labels = []
    print(f"\n데이터셋 스캔 시작: {dataset_path}")
    
    for class_index, class_name in enumerate(class_names):
        class_folder = os.path.join(dataset_path, class_name)
        if not os.path.exists(class_folder):
            print(f"error: {class_folder} 폴더를 찾을 수 없습니다. 건너뜁니다.")
            continue

        paths = glob.glob(os.path.join(class_folder, '*.wav')) + \
                glob.glob(os.path.join(class_folder, '*.mp3')) + \
                glob.glob(os.path.join(class_folder, '*.m4a')) + \
                glob.glob(os.path.join(class_folder, '*.aac'))
        
        file_paths.extend(paths)
        labels.extend([class_index] * len(paths))
        
    print(f"총 {len(file_paths)}개 파일 경로 확보.")
    return file_paths, labels

# 훈련시작
if __name__ == "__main__":

    BATCH_SIZE = 32 #일단 학습 시간땜에 16으로 잠시
    EPOCHS = 100
    LEARNING_RATE = 1e-3 #Adam 기본값 1e-3보다 조금 낮게 시작
    
    # 훈련용/검증용 파일 경로 분리
    all_files, all_labels = scan_dataset(DATASET_PATH, CLASS_NAMES)
    train_files, val_files, train_labels, val_labels = train_test_split(
        all_files, all_labels, 
        test_size=0.2, #8:2
        random_state=42, 
        stratify=all_labels
    )

    train_dataset = SoundDataGeneratorPyTorch(
        file_paths=train_files,
        labels=train_labels,
        target_length=AUDIO_LENGTH_SAMPLES,
        sample_rate=SAMPLE_RATE,
        augment=True
    )
    val_dataset = SoundDataGeneratorPyTorch(
        file_paths=val_files,
        labels=val_labels,
        target_length=AUDIO_LENGTH_SAMPLES,
        sample_rate=SAMPLE_RATE,
        augment=False
    )

    # Keras와 다르게 for문없이도 DataLoader함수가 배치처리, shuffle해줌.
    train_loader = DataLoader(
        dataset=train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=2
    )
    val_loader = DataLoader(
        dataset=val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=2
    )

# 클래스 불균형을 고려하여 훈련 데이터 라벨만 사용해서 가중치 계산
    class_weights_np = class_weight.compute_class_weight(
        'balanced',
        classes=np.unique(train_labels),
        y=train_labels
    )
    # NumPy -> Tensor
    class_weights_tensor = torch.tensor(class_weights_np, dtype=torch.float32)

    if torch.cuda.is_available():
        device = torch.device("cuda")
        print("훈련 장치: CUDA (NVIDIA GPU)")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        print("훈련 장치: MPS (Apple Silicon GPU)")
    else:
        device = torch.device("cpu")
        print("훈련 장치: CPU")

    # 클래스 가중치 텐서도 모델과 같은 장치로 이동
    class_weights_tensor = class_weights_tensor.to(device)

    model = PANNs_Tuned_Model(
        num_classes=NOISE_CLASSES,
        pann_weights_path=PANN_WEIGHTS_PATH
    )
    model = model.to(device) # 모델을 GPU/MPS/CPU로 이동

    # 옵티마이저 (Adam)
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()), # ‼️ requires_grad=True인 파라미터만 전달
        lr=LEARNING_RATE
    )
    
    # 손실 함수 (CrossEntropyLoss)
    criterion = nn.CrossEntropyLoss(weight=class_weights_tensor)

    #checkpoint (keras와 다르게 수동 구현)
    best_val_accuracy = 0.0
    os.makedirs('checkpoints', exist_ok=True)
    BEST_MODEL_PATH = 'checkpoints/best_model_pann.pth' # PyTorch 모델 저장 경로
    
    print(f"\n훈련 시작 (총 {EPOCHS} 에폭)")

    # Keras의 model.fit()과 다르게 수동 구현
    for epoch in range(EPOCHS):
        print(f"\n--- Epoch {epoch+1}/{EPOCHS} ---")
        
        #훈련단계
        model.train() # 모델을 훈련모드로 전환 (드롭아웃 같은 것들이 적용)
        running_loss = 0.0 # 에폭마다 초기화
        correct_preds = 0
        total_samples = 0
        
        train_pbar = tqdm(train_loader, desc=f"Epoch {epoch+1} [훈련]") # 진행률 표시
        
        for inputs, labels in train_pbar:
            inputs = inputs.to(device) # 데이터를 GPU/MPS/CPU로 이동
            labels = labels.to(device)
            
            optimizer.zero_grad() # 기울기 초기화
            
            outputs = model(inputs)  # 순전파 (모델 예측)  
            loss = criterion(outputs, labels) #loss 계산
            
            loss.backward() # 역전파
            
            optimizer.step() # 가중치 업데이트
            

            running_loss += loss.item() * inputs.size(0)
            
            _, predicted_indices = torch.max(outputs.data, 1) # 가장 높은 점수의 인덱스 
            total_samples += labels.size(0)
            correct_preds += (predicted_indices == labels).sum().item()

            train_pbar.set_postfix({'loss': f'{running_loss/total_samples:.4f}'})

        # 이번 에폭의 훈련 평균 손실과 정확도
        epoch_train_loss = running_loss / total_samples
        epoch_train_acc = (correct_preds / total_samples) * 100
        
        # 검증 단계
        model.eval() # 모델을 평가모드로 전환 (드롭아웃 꺼짐)
        running_val_loss = 0.0
        correct_val_preds = 0
        total_val_samples = 0
        
        val_pbar = tqdm(val_loader, desc=f"Epoch {epoch+1} [검증]")
        
        with torch.no_grad(): # 검증이기 때문에 기울기 계산 x
            for inputs, labels in val_pbar:
                inputs = inputs.to(device)
                labels = labels.to(device)
                
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
                running_val_loss += loss.item() * inputs.size(0)
                _, predicted_indices = torch.max(outputs.data, 1)
                total_val_samples += labels.size(0)
                correct_val_preds += (predicted_indices == labels).sum().item()
                val_pbar.set_postfix({'val_loss': f'{running_val_loss/total_val_samples:.4f}'})

        # 이번 에폭의 검증 평균 손실과 정확도
        epoch_val_loss = running_val_loss / total_val_samples
        epoch_val_acc = (correct_val_preds / total_val_samples) * 100
        
        # 결과 출력 및 checkpoint 갱신
        print(f"훈련 손실: {epoch_train_loss:.4f}, 훈련 정확도: {epoch_train_acc:.2f}%")
        print(f"검증 손실: {epoch_val_loss:.4f}, 검증 정확도: {epoch_val_acc:.2f}%")

        if epoch_val_acc > best_val_accuracy:
            best_val_accuracy = epoch_val_acc
            torch.save(model.state_dict(), BEST_MODEL_PATH)
            print(f"베스트모델 갱신 ({best_val_accuracy:.2f}%) -> '{BEST_MODEL_PATH}'에 저장됨.")

    print("\n--- 훈련 완료 ---")