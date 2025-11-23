import tensorflow as tf
import tensorflow_hub as hub

class YAMNetLayer(tf.keras.layers.Layer):
    """
    (batch_size, 15600) 모양의 원본 오디오(waveform) 배치를 입력받아
    (batch_size, 1, 1024) 모양의 YAMNet 임베딩(embeddings) 배치를 출력
    """
    def __init__(self, **kwargs):
        super(YAMNetLayer, self).__init__(**kwargs)
        self.yamnet_tf_function = hub.load('https://tfhub.dev/google/yamnet/1') # 모델로드
        self.trainable = False # 학습되지 않도록

    def call(self, inputs):
        # 배치 내의 각 샘플(15600,)에 대해 실행할 함수를 정의합니다.
        def run_yamnet_on_sample(waveform_1d):
            outputs_tuple = self.yamnet_tf_function(waveform_1d)
            return outputs_tuple[1] #YAMNet의 출력값에서 1024의 embedding값만 가져옴.

        # map_fn을 사용해 inputs의 모든 항목에 함수를 적용
        batch_embeddings = tf.map_fn(
            fn=run_yamnet_on_sample,
            elems=inputs,
            fn_output_signature=tf.TensorSpec(shape=(1, 1024), dtype=tf.float32)
        )
        return batch_embeddings #최종 결과 (batch_size, 1, 1024) 모양의 텐서를 반환.

    def compute_output_shape(self, input_shape):
        return (input_shape[0], 1, 1024)