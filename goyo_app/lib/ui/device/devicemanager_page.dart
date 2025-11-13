import 'package:flutter/material.dart';
import 'package:goyo_app/ui/device/widget/deviceinfo.dart';
import 'package:goyo_app/data/models/device_models.dart';
import 'package:goyo_app/data/services/api_service.dart';

enum DeviceKind { mic, spk }

enum DeviceStatus { connected, disconnected }

class AudioDevice {
  final String id;
  final String name;
  final DeviceKind kind;
  DeviceStatus status;

  AudioDevice({
    required this.id,
    required this.name,
    required this.kind,
    required this.status,
  });
}

class DeviceManager extends StatefulWidget {
  const DeviceManager({super.key});

  @override
  State<DeviceManager> createState() => _DeviceManagerPageState();
}

class _DeviceManagerPageState extends State<DeviceManager> {
  final ApiService _api = ApiService();
  bool scanning = false;
  bool _initialLoading = true;

  // ✅ 기본 디바이스(테스트용): 마이크 1, 스피커 1
  final List<AudioDevice> devices = [
    AudioDevice(
      id: 'mic-01',
      name: 'Room Mic',
      kind: DeviceKind.mic,
      status: DeviceStatus.disconnected,
    ),
    AudioDevice(
      id: 'spk-01',
      name: 'Desk Speaker',
      kind: DeviceKind.spk,
      status: DeviceStatus.connected,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      // ✅ AppBar 제거
      body: SafeArea(
        child: Column(
          children: [
            // ✅ 상단 오른쪽에 "Scan"만 배치
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton.icon(
                    onPressed: scanning ? null : _scanDevices,
                    icon: scanning
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.refresh),
                    label: Text(scanning ? 'Scanning...' : 'Scan'),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),

            // 목록
            Expanded(
              child: ListView.separated(
                itemCount: devices.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, i) {
                  final d = devices[i];
                  final isConn = d.status == DeviceStatus.connected;
                  return ListTile(
                    leading: Icon(
                      d.kind == DeviceKind.mic
                          ? Icons.mic
                          : Icons.speaker_outlined,
                      color: cs.primary,
                    ),
                    title: Text(d.name, style: const TextStyle(fontSize: 18)),
                    subtitle: Text(
                      isConn ? 'Connected' : 'Not Connected',
                      style: TextStyle(
                        color: isConn ? cs.primary : cs.onSurfaceVariant,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    trailing: IconButton(
                      icon: const Icon(Icons.info_outline),
                      onPressed: () async {
                        final res = await Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => DeviceInfo(device: d),
                          ),
                        );

                        if (res is Map && res['deletedId'] == d.id) {
                          setState(
                            () => devices.removeWhere((x) => x.id == d.id),
                          );
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Deleted "${d.name}"')),
                          );
                        }
                      },
                    ),
                    onTap: () {
                      // (옵션) 탭해서 연결 토글 – 필요 없으면 삭제 가능
                      setState(() {
                        d.status = isConn
                            ? DeviceStatus.disconnected
                            : DeviceStatus.connected;
                      });
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 스캔으로만 추가되는 플로우(데모)
  Future<void> _scanDevices() async {
    setState(() => scanning = true);
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;

    // 데모: 스캔으로 임의 디바이스 1개 추가
    setState(() {
      devices.add(
        AudioDevice(
          id: 'spk-${DateTime.now().millisecondsSinceEpoch}',
          name: 'Livingroom Speaker',
          kind: DeviceKind.spk,
          status: DeviceStatus.disconnected,
        ),
      );
      scanning = false;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Scan complete: 1 device found (demo)')),
    );
  }
}
