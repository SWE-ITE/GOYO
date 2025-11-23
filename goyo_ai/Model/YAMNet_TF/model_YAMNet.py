import tensorflow as tf
import numpy as np
import os
import glob
from sklearn.utils import class_weight
from tensorflow.keras.callbacks import ModelCheckpoint
from sklearn.model_selection import train_test_split
from pathlib import Path
from layers import YAMNetLayer
from dataset_YAMNet import SoundDataGenerator

def scan_dataset(dataset_path, class_names):
    file_paths = []
    labels = []
    print(f"\n데이터셋 스캔 시작: {dataset_path}")
    
    for class_index, class_name in enumerate(class_names):
        class_folder = os.path.join(dataset_path, class_name)
        if not os.path.exists(class_folder):
            print(f"경고: {class_folder} 폴더를 찾을 수 없습니다. 건너뜁니다.")
            continue
        paths = glob.glob(os.path.join(class_folder, '*.wav')) + \
                glob.glob(os.path.join(class_folder, '*.mp3')) + \
                glob.glob(os.path.join(class_folder, '*.m4a')) + \
                glob.glob(os.path.join(class_folder, '*.aac'))
        file_paths.extend(paths)
        labels.extend([class_index] * len(paths))
        
    print(f"--- 스캔 완료. 총 {len(file_paths)}개 파일 경로 확보. ---")
    return file_paths, labels

SAMPLE_RATE = 16000
AUDIO_LENGTH_SAMPLES = 15600 # YAMNet의 윈도우 크기에 맞춘 값 (0.975초)
DATASET_PATH = Path(__file__).resolve().parent.parent.parent / 'Dataset' / 'Final_dataset'
CLASS_NAMES = [
    'Air_conditioner',
    'Hair_dryer',
    'Microwave',
    'Others', 
    'Refrigerator_Hum', 
    'Vacuum',
]
NOISE_CLASSES = len(CLASS_NAMES)

def build_finetuned_model(NOISE_CLASSES):
    inputs = tf.keras.layers.Input(shape=(AUDIO_LENGTH_SAMPLES,), dtype=tf.float32, name='audio_input')
    embeddings = YAMNetLayer()(inputs) 
    flattened_embeddings = tf.keras.layers.Flatten(name='flatten_embeddings')(embeddings)

    #은닉층
    x = tf.keras.layers.Dense(256, activation='relu', name='hidden_layer')(flattened_embeddings)
    x = tf.keras.layers.Dropout(0.5)(x) 

    outputs = tf.keras.layers.Dense(NOISE_CLASSES, activation='softmax', name='custom_classifier')(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name='yamnet_finetuned_v2')
    return model

model = build_finetuned_model(NOISE_CLASSES)
model.summary() # 학습시 모델 구조 확인할 것
model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy', 
    metrics=['accuracy']
)

# 데이터셋 스캔 및 분리, 훈련용과 검증용을 8:2 비율로 파일 경로 리스트를 분리 (그냥 데이터를 분리하는 것)
all_files, all_labels = scan_dataset(DATASET_PATH, CLASS_NAMES)
train_files, val_files, train_labels, val_labels = train_test_split(
    all_files, 
    all_labels, 
    test_size=0.2, # 전체에서 20%를 검증용으로 사용
    random_state=42, 
    stratify=all_labels #원본의 클래스 비율을 유지하며 분리
)

# 클래스 불균형을 고려하여 훈련 데이터 라벨만 사용해서 가중치 계산
class_weights = class_weight.compute_class_weight(
    'balanced', #데이터 개수에 반비례하게 가중치를 줌 (적을수록 많은 가중치)
    classes=np.unique(train_labels), # np.unique(y_train) -> train_labels
    y=train_labels                   # y_train -> train_labels
)
class_weight_dict = {i : class_weights[i] for i in range(len(class_weights))}
print(f"클래스 가중치 적용: {class_weight_dict}")


BATCH_SIZE = 32
# 훈련용 제너레이터
train_generator = SoundDataGenerator(
    file_paths=train_files,
    labels=train_labels,
    batch_size=BATCH_SIZE,
    target_length=AUDIO_LENGTH_SAMPLES,
    sample_rate=SAMPLE_RATE,
    class_names=CLASS_NAMES,
    augment=True
)
# 검증용 제너레이터
val_generator = SoundDataGenerator(
    file_paths=val_files,
    labels=val_labels,
    batch_size=BATCH_SIZE,
    target_length=AUDIO_LENGTH_SAMPLES,
    sample_rate=SAMPLE_RATE,
    class_names=CLASS_NAMES,
    augment=False
)

os.makedirs('checkpoints', exist_ok=True) #자동저장

checkpoint_cb = ModelCheckpoint(
    'checkpoints/best_model.keras',
    monitor='val_accuracy', #'accuracy'가 아닌 'val_accuracy'(검증 정확도)를 모니터링해야 함.(전자는 과적합 우려)
    save_best_only=True,
    mode='max',
    verbose=1
)

#start training
print("\n[Phase 1]")
# 모델 컴파일 (높은 학습률)
model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
              loss='sparse_categorical_crossentropy', 
              metrics=['accuracy'])

model.fit(
    train_generator,
    epochs=20, # phase1은 20 에폭만 진행
    class_weight=class_weight_dict,
    validation_data=val_generator,
    callbacks=[checkpoint_cb],
    steps_per_epoch=len(train_generator),
    validation_steps=len(val_generator)
)

print("[Phase 2](Unfreeze Backbone)")

yamnet_found = False
for layer in model.layers:
    # 레이어 이름에 'yamnet'이 있거나 타입이 YAMNetLayer면 품.
    if 'yamnet' in layer.name.lower() or 'YAMNetLayer' in str(type(layer)):
        layer.trainable = True
        yamnet_found = True
        print(f"-> Unfrozen Layer: {layer.name}")

if not yamnet_found:
    print("error: YAMNet 레이어를 찾지 못했습니다.")
    model.trainable = True

model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
              loss='sparse_categorical_crossentropy', 
              metrics=['accuracy'])

early_stop = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

model.fit(
    train_generator,
    initial_epoch=20, # 20부터 이어서 시작
    epochs=100,
    class_weight=class_weight_dict,
    validation_data=val_generator,
    callbacks=[checkpoint_cb, early_stop], # 콜백 추가
    steps_per_epoch=len(train_generator),
    validation_steps=len(val_generator)
)

print("훈련 완료.")