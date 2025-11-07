## How to run backend & AI server
```
docker-compose up
```

## Swagger UI
backend - http://localhost:8000/docs#/
AI - http://localhost:8001/docs#/

## Server Architecture
```
┌─────────────────────┐
│   Client App        │ (Flutter)
│   - 로그인/회원가입     │
│   - 디바이스 설정      │
│   - ANC 제어         │
└──────────┬──────────┘
           │ HTTP REST API
           ↓
┌─────────────────────┐     Redis Pub/Sub     ┌─────────────────────┐
│  Backend Server     │◄────────────────-────►│   AI Server         │
│  (Port 8000)        │                       │   (Port 8001)       │
│                     │  audio:source         │                     │
│  - JWT 인증          │  audio:reference      │  - 오디오 처리         │
│  - 디바이스 CRUD      │  anc:control          │  - ANC 알고리즘        │
│  - PyAudio 캡처      │  anc:result           │  - 노이즈 분석         │
│  - Redis 전송        │                       │  - 신호 생성           │
└──────────┬──────────┘                       └──────────┬──────────┘
           │                                             │
           ↓                                             ↓
    PostgreSQL                                      MQTT Broker
    (User/Device)                                        ↓
                                                   [Wi-Fi Speaker]

┌─────────────────────┐
│  USB 마이크           │
│  - Source Mic       │
│  - Reference Mic    │
└──────────┬──────────┘
           │ 노트북 USB 연결 (테스트)
           │ 라즈베리파이 연결 (프로덕션)
           ↓
     Backend (PyAudio)
```
----------------------------------------
# GOYO 서버 구현 가이드

**작성일**: 2025-01-20
**버전**: 3.5.0
**대상**: 프론트엔드, AI, 하드웨어 개발자

---

## 📋 목차

1. [시스템 개요](#시스템-개요)
2. [전체 아키텍처](#전체-아키텍처)
3. [Backend API 명세](#backend-api-명세)
4. [AI Server 명세](#ai-server-명세)
5. [데이터 포맷](#데이터-포맷)
6. [연동 가이드](#연동-가이드)
7. [테스트 방법](#테스트-방법)

---

## 시스템 개요

### GOYO란?
AI 기반 능동 소음 제어(ANC) 시스템으로, USB 마이크로 소음을 감지하고 Wi-Fi 스피커로 반대 위상의 소리를 출력하여 소음을 상쇄합니다.

### 시스템 구성

| 컴포넌트 | 역할 | 포트 | 기술 스택 |
|---------|------|------|----------|
| **Backend Server** | 인증, 디바이스 관리, 오디오 캡처 | 8000 | FastAPI, PostgreSQL, PyAudio |
| **AI Server** | 오디오 처리, ANC 신호 생성 | 8001 | FastAPI, Redis, NumPy |
| **PostgreSQL** | 사용자 및 디바이스 데이터 저장 | 5432 | - |
| **Redis** | Pub/Sub 메시지 브로커 | 6379 | - |
| **MQTT Broker** | 스피커 제어 (Phase 6) | 1883 | Mosquitto |
| **Client App** | 제어 인터페이스 | - | Flutter |

---

## 전체 아키텍처

### 시스템 흐름도

```
┌─────────────────────┐
│   Client App        │ (Flutter)
│   - 로그인/회원가입  │
│   - 디바이스 설정    │
│   - ANC 제어        │
└──────────┬──────────┘
           │ HTTP REST API
           ↓
┌─────────────────────┐     Redis Pub/Sub     ┌─────────────────────┐
│  Backend Server     │◄────────────────────►│   AI Server         │
│  (Port 8000)        │                       │   (Port 8001)       │
│                     │  audio:source         │                     │
│  - JWT 인증         │  audio:reference      │  - 오디오 처리       │
│  - 디바이스 CRUD    │  anc:control          │  - ANC 알고리즘     │
│  - PyAudio 캡처     │  anc:result           │  - 노이즈 분석      │
│  - Redis 전송       │                       │  - 신호 생성        │
└──────────┬──────────┘                       └──────────┬──────────┘
           │                                             │
           ↓                                             ↓
    PostgreSQL                                      MQTT Broker
    (User/Device)                                        ↓
                                                   [Wi-Fi Speaker]

┌─────────────────────┐
│  USB 마이크         │
│  - Source Mic       │
│  - Reference Mic    │
└──────────┬──────────┘
           │ 노트북 USB 연결 (테스트)
           │ 라즈베리파이 연결 (프로덕션)
           ↓
     Backend (PyAudio)
```

### 데이터 흐름

1. **사용자 인증**: Client → Backend (JWT 토큰 발급)
2. **디바이스 설정**: Client → Backend (USB 마이크/스피커 페어링)
3. **ANC 시작**: Client → Backend (start 명령)
4. **오디오 캡처**: USB 마이크 → Backend (PyAudio)
5. **오디오 전송**: Backend → Redis Pub/Sub → AI Server
6. **ANC 처리**: AI Server (노이즈 분석 + 역위상 신호 생성)
7. **스피커 출력**: AI Server → MQTT → Wi-Fi Speaker
8. **결과 전송**: AI Server → Redis → Backend → Client (모니터링)

---

## Backend API 명세

### Base URL
```
http://localhost:8000
```

### 인증 방식
모든 보호된 API는 JWT Bearer 토큰 필요:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

### 1. 인증 API

#### 1.1 회원가입
```http
POST /api/auth/signup

Request Body:
{
  "email": "user@example.com",
  "password": "password123",
  "name": "홍길동"
}

Response (200):
{
  "id": 1,
  "email": "user@example.com",
  "name": "홍길동",
  "anc_enabled": false,
  "anc_suppression_level": 80
}
```

#### 1.2 로그인
```http
POST /api/auth/login

Request Body:
{
  "email": "user@example.com",
  "password": "password123"
}

Response (200):
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "홍길동"
  }
}
```

---

### 2. 디바이스 관리 API

#### 2.1 USB 마이크 검색
```http
POST /api/devices/discover/usb
Headers: Authorization: Bearer {token}

Response (200):
{
  "devices": [
    {
      "device_id": "USB_MIC_0",
      "device_name": "USB Audio Device",
      "device_type": "microphone_unknown",
      "connection_type": "usb",
      "index": 0,
      "channels": 1,
      "sample_rate": 44100
    },
    {
      "device_id": "USB_MIC_1",
      "device_name": "USB Audio Device",
      "device_type": "microphone_unknown",
      "connection_type": "usb",
      "index": 1,
      "channels": 1,
      "sample_rate": 44100
    }
  ]
}
```

#### 2.2 Wi-Fi 스피커 검색
```http
POST /api/devices/discover/wifi
Headers: Authorization: Bearer {token}

Response (200):
{
  "devices": [
    {
      "device_id": "SPK_192.168.1.100",
      "device_name": "GOYO Speaker",
      "device_type": "speaker",
      "connection_type": "wifi",
      "ip": "192.168.1.100"
    }
  ]
}
```

#### 2.3 디바이스 페어링
```http
POST /api/devices/pair
Headers: Authorization: Bearer {token}

Request Body:
{
  "device_id": "USB_MIC_0",
  "device_name": "USB Audio Device",
  "device_type": "microphone_source",
  "connection_type": "usb"
}

Response (200):
{
  "id": 1,
  "device_id": "USB_MIC_0",
  "device_name": "USB Audio Device",
  "device_type": "microphone_source",
  "is_connected": false,
  "connection_type": "usb"
}
```

#### 2.4 마이크 역할 지정
```http
PUT /api/devices/microphone/{device_id}/role?role=microphone_source
Headers: Authorization: Bearer {token}

Response (200):
{
  "success": true,
  "device_id": "USB_MIC_0",
  "new_role": "microphone_source"
}
```

**역할 종류**:
- `microphone_source`: 소음 측정용 메인 마이크
- `microphone_reference`: 참조용 보조 마이크

#### 2.5 디바이스 구성 확인
```http
GET /api/devices/setup
Headers: Authorization: Bearer {token}

Response (200):
{
  "is_complete": true,
  "source_microphone": {
    "device_id": "USB_MIC_0",
    "device_name": "USB Audio Device"
  },
  "reference_microphone": {
    "device_id": "USB_MIC_1",
    "device_name": "USB Audio Device"
  },
  "speaker": {
    "device_id": "SPK_192.168.1.100",
    "device_name": "GOYO Speaker"
  }
}
```

---

### 3. 프로필 관리 API

#### 3.1 프로필 조회
```http
GET /api/profile
Headers: Authorization: Bearer {token}

Response (200):
{
  "id": 1,
  "email": "user@example.com",
  "name": "홍길동",
  "anc_enabled": true,
  "anc_suppression_level": 85
}
```

#### 3.2 ANC ON/OFF 토글
```http
POST /api/profile/anc/toggle
Headers: Authorization: Bearer {token}

Request Body:
{
  "enabled": true
}

Response (200):
{
  "success": true,
  "anc_enabled": true
}
```

#### 3.3 ANC 억제 강도 설정
```http
PUT /api/profile/anc/suppression
Headers: Authorization: Bearer {token}

Request Body:
{
  "level": 85
}

Response (200):
{
  "success": true,
  "anc_suppression_level": 85
}
```

**억제 강도**: 0 ~ 100 (높을수록 강력한 노이즈 제거)

---

### 4. 오디오 제어 API

#### 4.1 ANC 시작
```http
POST /api/audio/start
Headers: Authorization: Bearer {token}

Response (200):
{
  "success": true,
  "message": "Audio streaming started",
  "source_device": "USB Audio Device",
  "reference_device": "USB Audio Device",
  "speaker": "GOYO Speaker",
  "source_device_index": 0,
  "reference_device_index": 1
}

Error (400):
{
  "detail": "Device setup incomplete. Please pair source mic, reference mic, and speaker."
}
```

**동작**:
1. Backend가 USB 마이크 2개에서 동시에 오디오 캡처 시작
2. Redis Pub/Sub으로 AI Server에 실시간 오디오 스트림 전송
3. AI Server에 ANC 시작 제어 명령 전송

#### 4.2 ANC 중지
```http
POST /api/audio/stop
Headers: Authorization: Bearer {token}

Response (200):
{
  "success": true,
  "message": "Audio streaming stopped"
}
```

#### 4.3 실시간 모니터링 (WebSocket)
```javascript
const ws = new WebSocket('ws://localhost:8000/api/audio/ws/monitor');

ws.onopen = () => {
  // 인증 메시지 전송
  ws.send(JSON.stringify({
    user_id: "1"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('ANC Status:', data);
  // {
  //   "timestamp": 1704067200.123,
  //   "noise_level_db": 65.2,
  //   "reduction_db": 12.5,
  //   "status": "active"
  // }
};
```

---

## AI Server 명세

### Base URL
```
http://localhost:8001
```

### 1. Health Check

#### 1.1 기본 헬스 체크
```http
GET /

Response (200):
{
  "service": "GOYO AI Server",
  "status": "running",
  "version": "1.0.0"
}
```

#### 1.2 상세 헬스 체크
```http
GET /health

Response (200):
{
  "status": "healthy",
  "redis": true,
  "audio_processor": true,
  "active_sessions": 2
}
```

### 2. 실시간 모니터링 (WebSocket)

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/monitor/1'); // user_id=1

ws.onmessage = (event) => {
  const status = JSON.parse(event.data);
  console.log('Processing Status:', status);
  // AI Server의 실시간 처리 상태
};
```

---

## 데이터 포맷

### 1. Redis Pub/Sub 채널

#### Backend → AI Server

**Channel: `audio:source`**
```json
{
  "user_id": "1",
  "audio_data": "AAABAAEAAAABAA...",
  "timestamp": 1704067200.123,
  "sample_rate": 44100,
  "channels": 1
}
```
- `audio_data`: Base64 인코딩된 PCM16 오디오 데이터
- `timestamp`: UNIX 타임스탬프 (초 단위, 소수점 포함)
- `sample_rate`: 샘플링 레이트 (44100 Hz)
- `channels`: 채널 수 (1 = Mono)

**Channel: `audio:reference`**
```json
{
  "user_id": "1",
  "audio_data": "AAABAAEAAAABAA...",
  "timestamp": 1704067200.123,
  "sample_rate": 44100,
  "channels": 1
}
```

**Channel: `anc:control`**
```json
{
  "user_id": "1",
  "command": "start",
  "params": {
    "suppression_level": 85
  }
}
```
- `command`: "start", "stop", "adjust"
- `params`: 명령별 파라미터

#### AI Server → Backend

**Channel: `anc:result`**
```json
{
  "user_id": "1",
  "timestamp": 1704067200.456,
  "noise_level_db": 65.2,
  "reduction_db": 12.5,
  "status": "active"
}
```
- `noise_level_db`: 현재 소음 레벨 (dB SPL)
- `reduction_db`: 감소된 소음량 (dB)
- `status`: "active", "processing", "stopped"

---

### 2. 오디오 데이터 상세

**포맷**: PCM16 (16-bit signed integer)
**샘플링 레이트**: 44100 Hz
**채널**: Mono (1 채널)
**청크 크기**: 4096 샘플 (약 93ms @ 44.1kHz)
**인코딩**: Base64

**예시 (Python)**:
```python
import base64
import numpy as np

# 오디오 데이터 생성 (int16)
audio_data = np.random.randint(-32768, 32767, 4096, dtype=np.int16)

# Base64 인코딩
audio_bytes = audio_data.tobytes()
audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

# 전송
message = {
    "user_id": "1",
    "audio_data": audio_base64,
    "timestamp": time.time(),
    "sample_rate": 44100,
    "channels": 1
}
```

**디코딩 (Python)**:
```python
import base64
import numpy as np

# Base64 디코딩
audio_bytes = base64.b64decode(message["audio_data"])
audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

# 이제 audio_data는 4096개의 int16 샘플
```

---

## 연동 가이드

### 프론트엔드 (Flutter) 연동

#### 1. 로그인 플로우

```dart
// 1. 회원가입
final signupResponse = await http.post(
  Uri.parse('http://localhost:8000/api/auth/signup'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({
    'email': 'user@example.com',
    'password': 'password123',
    'name': '홍길동'
  }),
);

// 2. 로그인
final loginResponse = await http.post(
  Uri.parse('http://localhost:8000/api/auth/login'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({
    'email': 'user@example.com',
    'password': 'password123'
  }),
);

final token = jsonDecode(loginResponse.body)['access_token'];

// 3. 이후 모든 API 호출 시 토큰 사용
final response = await http.get(
  Uri.parse('http://localhost:8000/api/profile'),
  headers: {
    'Authorization': 'Bearer $token',
  },
);
```

#### 2. 디바이스 설정 플로우

```dart
// 1. USB 마이크 검색
final usbResponse = await http.post(
  Uri.parse('http://localhost:8000/api/devices/discover/usb'),
  headers: {'Authorization': 'Bearer $token'},
);

final usbDevices = jsonDecode(usbResponse.body)['devices'];

// 2. 마이크 2개 페어링
for (var device in usbDevices) {
  await http.post(
    Uri.parse('http://localhost:8000/api/devices/pair'),
    headers: {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    },
    body: jsonEncode({
      'device_id': device['device_id'],
      'device_name': device['device_name'],
      'device_type': 'microphone_unknown',
      'connection_type': 'usb',
    }),
  );
}

// 3. 역할 지정
await http.put(
  Uri.parse('http://localhost:8000/api/devices/microphone/${usbDevices[0]['device_id']}/role?role=microphone_source'),
  headers: {'Authorization': 'Bearer $token'},
);

await http.put(
  Uri.parse('http://localhost:8000/api/devices/microphone/${usbDevices[1]['device_id']}/role?role=microphone_reference'),
  headers: {'Authorization': 'Bearer $token'},
);

// 4. Wi-Fi 스피커 검색 및 페어링
final wifiResponse = await http.post(
  Uri.parse('http://localhost:8000/api/devices/discover/wifi'),
  headers: {'Authorization': 'Bearer $token'},
);

final speaker = jsonDecode(wifiResponse.body)['devices'][0];

await http.post(
  Uri.parse('http://localhost:8000/api/devices/pair'),
  headers: {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  },
  body: jsonEncode({
    'device_id': speaker['device_id'],
    'device_name': speaker['device_name'],
    'device_type': 'speaker',
    'connection_type': 'wifi',
  }),
);
```

#### 3. ANC 제어 플로우

```dart
// 1. ANC ON
await http.post(
  Uri.parse('http://localhost:8000/api/profile/anc/toggle'),
  headers: {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  },
  body: jsonEncode({'enabled': true}),
);

// 2. 억제 강도 설정
await http.put(
  Uri.parse('http://localhost:8000/api/profile/anc/suppression'),
  headers: {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  },
  body: jsonEncode({'level': 85}),
);

// 3. ANC 시작
final startResponse = await http.post(
  Uri.parse('http://localhost:8000/api/audio/start'),
  headers: {'Authorization': 'Bearer $token'},
);

// 4. ANC 중지
await http.post(
  Uri.parse('http://localhost:8000/api/audio/stop'),
  headers: {'Authorization': 'Bearer $token'},
);
```

#### 4. 실시간 모니터링 (WebSocket)

```dart
import 'package:web_socket_channel/web_socket_channel.dart';

final channel = WebSocketChannel.connect(
  Uri.parse('ws://localhost:8000/api/audio/ws/monitor'),
);

// 인증
channel.sink.add(jsonEncode({'user_id': '1'}));

// 메시지 수신
channel.stream.listen((message) {
  final data = jsonDecode(message);
  print('Noise Level: ${data['noise_level_db']} dB');
  print('Reduction: ${data['reduction_db']} dB');
});
```

---

### AI 팀 연동

#### 1. Redis Pub/Sub 리스너 수정

AI 팀이 작업할 파일: `ai/main.py`

**오디오 데이터 수신 핸들러**:
```python
async def handle_source_audio(data: dict):
    """Source 마이크 오디오 처리"""
    user_id = data.get("user_id")
    audio_base64 = data.get("audio_data")
    timestamp = data.get("timestamp")

    # Base64 디코딩
    audio_bytes = base64.b64decode(audio_base64)
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

    # TODO: 여기서 AI 팀이 오디오 처리
    # - 노이즈 분류
    # - FFT 분석
    # - 특징 추출 등

    audio_processor.process_source(user_id, audio_array, timestamp)
```

**ANC 신호 생성**:
```python
# ai/anc_controller.py

class ANCController:
    def generate_anti_noise(self, source_data: np.ndarray, reference_data: np.ndarray) -> bytes:
        """
        ANC 신호 생성 (AI 팀이 구현)

        Args:
            source_data: Source 마이크 오디오 (numpy array, int16)
            reference_data: Reference 마이크 오디오 (numpy array, int16)

        Returns:
            bytes: 안티-노이즈 신호 (PCM16, 스피커로 전송)
        """

        # TODO: AI 팀 구현
        # 1. 노이즈 분류 (CNN 모델)
        # 2. 공간 전달 함수 계산
        # 3. FxLMS 적응 필터
        # 4. 역위상 신호 생성

        # 현재는 기본 역위상 (180도 위상 반전)
        anti_noise = -source_data

        return anti_noise.tobytes()
```

#### 2. 결과 전송

```python
# AI 처리 결과를 Backend에 전송
await redis_client.publish(
    "anc:result",
    json.dumps({
        "user_id": user_id,
        "timestamp": time.time(),
        "noise_level_db": 65.2,  # 계산된 노이즈 레벨
        "reduction_db": 12.5,    # 계산된 감소량
        "status": "active"
    })
)
```

---

### 하드웨어 팀 (라즈베리파이) 연동

#### 라즈베리파이로 전환 시

현재는 노트북에서 Backend가 USB 마이크를 직접 캡처하지만, 나중에는:

```
라즈베리파이 + USB 마이크
    ↓
라즈베리파이에서 PyAudio 캡처
    ↓
Redis Pub/Sub으로 AI 서버에 전송
```

**필요한 작업**:
1. `backend/app/services/audio_streaming_service.py` 파일을 라즈베리파이에 복사
2. Redis 연결 정보 변경 (라즈베리파이 → AI 서버)
3. 동일한 채널 포맷 사용: `audio:source`, `audio:reference`

**라즈베리파이 예시 코드**:
```python
# 라즈베리파이에서 실행
import redis
import pyaudio
import base64
import json
import time

# Redis 연결
redis_client = redis.Redis(
    host='AI_SERVER_IP',  # AI 서버 IP
    port=6379,
    decode_responses=False
)

# PyAudio 설정
p = pyaudio.PyAudio()
source_stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100,
                       input=True, input_device_index=0, frames_per_buffer=4096)
reference_stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100,
                          input=True, input_device_index=1, frames_per_buffer=4096)

user_id = "1"

while True:
    # 오디오 캡처
    source_data = source_stream.read(4096)
    reference_data = reference_stream.read(4096)

    # Redis 전송
    redis_client.publish("audio:source", json.dumps({
        "user_id": user_id,
        "audio_data": base64.b64encode(source_data).decode('utf-8'),
        "timestamp": time.time(),
        "sample_rate": 44100,
        "channels": 1
    }))

    redis_client.publish("audio:reference", json.dumps({
        "user_id": user_id,
        "audio_data": base64.b64encode(reference_data).decode('utf-8'),
        "timestamp": time.time(),
        "sample_rate": 44100,
        "channels": 1
    }))
```

---

## 테스트 방법

### 1. 서버 실행

#### Docker 서비스 시작
```bash
cd goyo-server
docker-compose up -d
```

#### Backend 서버 실행
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### AI 서버 실행
```bash
cd ai
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 2. Swagger UI 접속

- **Backend API**: http://localhost:8000/docs
- **AI Server**: http://localhost:8001/docs

### 3. USB 마이크 확인

```bash
python -c "import pyaudio; p = pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

### 4. API 테스트 (Postman/curl)

#### 회원가입
```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","name":"테스터"}'
```

#### 로그인
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'
```

#### USB 마이크 검색
```bash
curl -X POST http://localhost:8000/api/devices/discover/usb \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### ANC 시작
```bash
curl -X POST http://localhost:8000/api/audio/start \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Redis 모니터링

```bash
# Redis에 전송되는 메시지 실시간 확인
docker exec -it goyo_redis redis-cli MONITOR
```

### 6. 로그 확인

```bash
# Backend 로그
# 터미널에서 실시간 확인

# AI Server 로그
# 터미널에서 실시간 확인

# Docker 로그
docker-compose logs -f backend
docker-compose logs -f ai-server
```

---

## 환경 변수 설정

### Backend (.env)
```env
DATABASE_URL=postgresql://goyo_user:goyo_password@localhost:5432/goyo_db
REDIS_HOST=localhost
REDIS_PORT=6379
SECRET_KEY=your-secret-key-here-change-in-production
```

### AI Server (.env)
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

---

## 에러 코드

| 상태 코드 | 설명 |
|----------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (디바이스 미설정 등) |
| 401 | 인증 실패 (토큰 없음/만료) |
| 404 | 리소스 없음 |
| 500 | 서버 내부 에러 |

---

## 버전 히스토리

- **v3.5.0** (2025-11-05): Backend 오디오 캡처 및 Redis Pub/Sub 구현
- **v3.0.0** (2025-11-01): AI Server 분리, 기본 ANC 구현
- **v2.0.0** (2025-10-24): 디바이스 관리 및 프로필 API
- **v1.0.0** (2025-10-23): 인증 API 구현

---

**Last Updated**: 2025-11-06
**Document Version**: 1.0
