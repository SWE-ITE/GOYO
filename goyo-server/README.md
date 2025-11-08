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