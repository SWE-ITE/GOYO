## How to run backend & AI server
```
docker-compose up
```

## System Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Application                      │
│                     (React Web / Mobile App)                    │
└────────────┬───────────────────────────────────┬────────────────┘
             │                                   │
             │ HTTP/WS (제어)                     │ WebSocket (오디오)
             │ - 인증                             │ - 실시간 스트림
             │ - 디바이스 설정                      │
             │ - ANC 제어                         │
             ↓                                   ↓
    ┌─────────────────┐                 ┌──────────────────────┐
    │ FastAPI Backend │                 │     AI Server        │
    │  (Port 8000)    │                 │    (Port 8001)       │
    │                 │                 │                      │
    │ - JWT Auth      │◄─Redis Pub/Sub─►│ - Audio Stream RX    │
    │ - Device CRUD   │                 │ - ANC Processing     │
    │ - Profile API   │  anc:control    │ - Noise Detection    │
    │ - Statistics    │  anc:result     │ - Signal Generation  │
    │ - Monitoring    │  device:status  │                      │
    └────────┬────────┘                 └──────────┬───────────┘
             │                                     │
             ↓                                     ↓
       PostgreSQL                             MQTT Broker
       (User/Device)                               ↓
                                               [Speaker]
```
