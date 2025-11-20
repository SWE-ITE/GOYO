import torch
import torch.nn as nn
import os
import sys

try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
    pann_pytorch_dir = os.path.join(script_dir, "..", "audioset_tagging_cnn", "pytorch") # audioset_tagging_cnn다운로드 후 본인 경로 맞춰서 수정
    
    if not os.path.exists(os.path.join(pann_pytorch_dir, "models.py")):
        raise ImportError("PANNs 'audioset_tagging_cnn/pytorch' 폴더를 찾을 수 없습니다.")

    sys.path.append(pann_pytorch_dir)
    
    import models # PANNs의 models.py에서 Cnn14를 가져옴
    print("PANNs 'models.py' is successfully imported.")

except ImportError as e:
    print(f"PANNs import Failure: {e}")
    print("'audioset_tagging_cnn' 폴더의 위치를 확인하세요.")
    raise e #프로그램 강제종료



class PANNs_Tuned_Model(nn.Module):
    def __init__(self, num_classes, pann_weights_path):
        super(PANNs_Tuned_Model, self).__init__()
        
        self.pann_frontend = models.Cnn14(
            sample_rate=16000, 
            window_size=512, 
            hop_size=160, 
            mel_bins=64, 
            fmin=50, 
            fmax=8000, 
            classes_num=527
        )
        
        #이미 학습돼있는 PANN 가중치 로드
        print(f"PANNs 가중치 로드 중: {pann_weights_path}")
        try:
            checkpoint = torch.load(
                pann_weights_path, 
                map_location=torch.device('cpu'), 
                weights_only=False #'weights_only=False'를 명시적으로 추가하여 Unpickler 오류 해결
            )
            
            self.pann_frontend.load_state_dict(checkpoint['model'])
            print("PANNs 가중치 로드 성공.")
            
        except Exception as e:
            print(f"PANNs 가중치 로드 실패: {e}")

        # 이미 학습된 가중치들을 frozen (Keras의 trainable=False와 동일)
        for param in self.pann_frontend.parameters():
            param.requires_grad = False
        
        pann_embedding_size = 2048 #YAMNet의 임베딩은 1024인 것과 달리 PANN은 2048

        self.hidden_layer = nn.Linear(pann_embedding_size, 256)

        self.dropout = nn.Dropout(0.3) #overfitting 해결위해
        
        self.output_layer = nn.Linear(256, num_classes) #256 -> 20 (최종 클래스 갯수)

    def forward(self, x): # x의 형태: (BatchSize, 15600)

        pann_output = self.pann_frontend(x, None) 
        embedding = pann_output['embedding']
        x = self.hidden_layer(embedding)
        x = torch.relu(x)
        x = self.dropout(x)
        x = self.output_layer(x)

        return x