import 'package:flutter/material.dart';

/// Device Manager:
/// - 마이크/스피커 목록
/// - 연결/해제
/// - 입출력 테스트
/// - 지연(레이턴시) 보정
/// - 디바이스 추가/삭제
class DeviceManager extends StatefulWidget {
  const DeviceManager({super.key});

  @override
  State<DeviceManager> createState() => _DeviceManagerTabState();
}

class _DeviceManagerTabState extends State<DeviceManager> {
  bool scanning = false;

  final List<AudioDevice> devices = [
    AudioDevice(
      id: 'mic-01',
      name: 'Room Mic',
      kind: DeviceKind.mic,
      transport: Transport.wifi,
      status: DeviceStatus.connected,
      latencyMs: 28,
    ),
    AudioDevice(
      id: 'spk-01',
      name: 'Desk Speaker',
      kind: DeviceKind.spk,
      transport: Transport.ble,
      status: DeviceStatus.active,
      latencyMs: 36,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // 상단 액션: 스캔 + 디바이스 추가
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: scanning ? null : _scanDevices,
                icon: scanning
                    ? const SizedBox(
                        height: 16,
                        width: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh),
                label: Text(scanning ? 'Scanning...' : 'Scan devices'),
              ),
            ),
            const SizedBox(width: 12),
            OutlinedButton.icon(
              onPressed: _addDeviceDialog,
              icon: const Icon(Icons.add),
              label: const Text('Add device'),
            ),
          ],
        ),
        const SizedBox(height: 16),

        // 디바이스 리스트
        ...devices.map(
          (d) => _DeviceTile(
            device: d,
            onToggleConnection: () => _toggleConnection(d),
            onTest: () => _testDevice(d),
            onCalibrate: () => _calibrateLatency(d),
            onDelete: () => _deleteDevice(d),
            onRename: () => _renameDevice(d),
          ),
        ),
        if (devices.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 40),
            child: Center(
              child: Column(
                children: [
                  Icon(
                    Icons.speaker_notes_off,
                    color: cs.onSurfaceVariant,
                    size: 40,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'No devices found',
                    style: TextStyle(color: cs.onSurfaceVariant),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Future<void> _scanDevices() async {
    setState(() => scanning = true);
    await Future.delayed(const Duration(seconds: 1));
    if (!mounted) return;
    setState(() => scanning = false);
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Scan complete (demo)')));
  }

  void _toggleConnection(AudioDevice d) {
    setState(() {
      if (d.status == DeviceStatus.disconnected) {
        d.status = DeviceStatus.connected;
      } else {
        d.status = DeviceStatus.disconnected;
      }
    });
  }

  Future<void> _testDevice(AudioDevice d) async {
    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(
          'Test ${d.kind == DeviceKind.mic ? "microphone" : "speaker"}',
        ),
        content: Text(
          d.kind == DeviceKind.mic
              ? '🎙️ Listening for input... (demo)'
              : '🔊 Playing test tone... (demo)',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _calibrateLatency(AudioDevice d) async {
    if (d.kind == DeviceKind.mic) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Select a speaker to ping for latency (demo)'),
        ),
      );
      return;
    }
    final cs = Theme.of(context).colorScheme;
    int latency = d.latencyMs ?? 30;

    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (_) => StatefulBuilder(
        builder: (context, setSheet) {
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Icon(Icons.speed, color: cs.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Latency calibration',
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        color: cs.onSurface,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  'Estimated latency: $latency ms',
                  style: TextStyle(color: cs.onSurfaceVariant),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () async {
                    setSheet(() {}); // rebuild
                    await Future.delayed(const Duration(milliseconds: 600));
                    latency = 20 + (DateTime.now().millisecond % 25); // demo 값
                    setSheet(() {});
                  },
                  icon: const Icon(Icons.adjust),
                  label: const Text('Measure ping (demo)'),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: () {
                    setState(() => d.latencyMs = latency);
                    Navigator.pop(context);
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Saved latency: ${d.latencyMs} ms'),
                      ),
                    );
                  },
                  child: const Text('Save'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _addDeviceDialog() async {
    final nameCtrl = TextEditingController();
    Transport transport = Transport.wifi;
    DeviceKind kind = DeviceKind.mic;

    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (_) => Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 8,
          bottom: 16 + MediaQuery.of(context).viewInsets.bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 12),
            TextField(
              controller: nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Device name',
                hintText: 'e.g., Bedroom Speaker',
                prefixIcon: Icon(Icons.badge_outlined),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<DeviceKind>(
                    value: kind,
                    decoration: const InputDecoration(labelText: 'Kind'),
                    items: const [
                      DropdownMenuItem(
                        value: DeviceKind.mic,
                        child: Text('Microphone'),
                      ),
                      DropdownMenuItem(
                        value: DeviceKind.spk,
                        child: Text('Speaker'),
                      ),
                    ],
                    onChanged: (v) => kind = v ?? DeviceKind.mic,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: DropdownButtonFormField<Transport>(
                    value: transport,
                    decoration: const InputDecoration(labelText: 'Transport'),
                    items: const [
                      DropdownMenuItem(
                        value: Transport.wifi,
                        child: Text('Wi-Fi'),
                      ),
                      DropdownMenuItem(
                        value: Transport.ble,
                        child: Text('BLE'),
                      ),
                    ],
                    onChanged: (v) => transport = v ?? Transport.wifi,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () {
                final name = nameCtrl.text.trim().isEmpty
                    ? 'New Device'
                    : nameCtrl.text.trim();
                setState(() {
                  devices.add(
                    AudioDevice(
                      id: 'dev-${DateTime.now().millisecondsSinceEpoch}',
                      name: name,
                      kind: kind,
                      transport: transport,
                      status: DeviceStatus.disconnected,
                      latencyMs: null,
                    ),
                  );
                });
                Navigator.pop(context);
              },
              icon: const Icon(Icons.save_outlined),
              label: const Text('Add'),
            ),
          ],
        ),
      ),
    );
  }

  void _deleteDevice(AudioDevice d) {
    setState(() => devices.remove(d));
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('Deleted "${d.name}"')));
  }

  Future<void> _renameDevice(AudioDevice d) async {
    final ctrl = TextEditingController(text: d.name);
    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Rename device'),
        content: TextField(
          controller: ctrl,
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.edit_outlined),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              setState(
                () => d.name = ctrl.text.trim().isEmpty
                    ? d.name
                    : ctrl.text.trim(),
              );
              Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }
}

/// 개별 디바이스 카드
class _DeviceTile extends StatelessWidget {
  final AudioDevice device;
  final VoidCallback onToggleConnection;
  final VoidCallback onTest;
  final VoidCallback onCalibrate;
  final VoidCallback onDelete;
  final VoidCallback onRename;

  const _DeviceTile({
    required this.device,
    required this.onToggleConnection,
    required this.onTest,
    required this.onCalibrate,
    required this.onDelete,
    required this.onRename,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: ListTile(
          leading: CircleAvatar(
            backgroundColor: cs.primary.withOpacity(.12),
            child: Icon(
              device.kind == DeviceKind.mic
                  ? Icons.mic
                  : Icons.speaker_outlined,
              color: cs.primary,
            ),
          ),
          title: Text(
            device.name,
            softWrap: false,
            overflow: TextOverflow.ellipsis,
          ),
          subtitle: Wrap(
            spacing: 8,
            runSpacing: 0,
            children: [
              _Chip(
                text: _statusText(device.status),
                color: _statusColor(cs, device.status),
              ),
              _Chip(
                text: device.transport.name.toUpperCase(),
                color: cs.secondaryContainer,
              ),
              if (device.latencyMs != null)
                _Chip(
                  text: '${device.latencyMs} ms',
                  color: cs.tertiaryContainer,
                ),
            ],
          ),
          trailing: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.3, // ~화면 절반 정도
              // 혹은 const BoxConstraints(maxWidth: 180);
            ),
            child: Wrap(
              spacing: 0,
              runSpacing: 0,
              alignment: WrapAlignment.end,
              children: [
                IconButton(
                  tooltip: 'Rename',
                  onPressed: onRename,
                  icon: const Icon(Icons.edit_outlined),
                ),
                IconButton(
                  tooltip: device.status == DeviceStatus.disconnected
                      ? 'Connect'
                      : 'Disconnect',
                  onPressed: onToggleConnection,
                  icon: Icon(
                    device.status == DeviceStatus.disconnected
                        ? Icons.link
                        : Icons.link_off,
                  ),
                ),
                IconButton(
                  tooltip: device.kind == DeviceKind.mic
                      ? 'Input test'
                      : 'Output test',
                  onPressed: onTest,
                  icon: Icon(
                    device.kind == DeviceKind.mic
                        ? Icons.mic_none
                        : Icons.volume_up_outlined,
                  ),
                ),
                IconButton(
                  tooltip: 'Delete',
                  onPressed: onDelete,
                  icon: const Icon(Icons.delete_outline),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _statusText(DeviceStatus s) {
    switch (s) {
      case DeviceStatus.connected:
        return 'Connected';
      case DeviceStatus.active:
        return 'Active';
      case DeviceStatus.disconnected:
        return 'Disconnected';
    }
  }

  Color _statusColor(ColorScheme cs, DeviceStatus s) {
    switch (s) {
      case DeviceStatus.connected:
        return cs.secondaryContainer;
      case DeviceStatus.active:
        return cs.primaryContainer;
      case DeviceStatus.disconnected:
        return cs.errorContainer;
    }
  }
}

class _Chip extends StatelessWidget {
  final String text;
  final Color color;
  const _Chip({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    final on = ThemeData.estimateBrightnessForColor(color) == Brightness.dark
        ? Colors.white
        : Colors.black.withOpacity(.8);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      margin: const EdgeInsets.only(top: 8),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(text, style: TextStyle(fontSize: 12, color: on)),
    );
  }
}

/// ---- 모델/타입 (UI 더미) ----
enum DeviceKind { mic, spk }

enum Transport { wifi, ble }

enum DeviceStatus { disconnected, connected, active }

class AudioDevice {
  String id;
  String name;
  DeviceKind kind;
  Transport transport;
  DeviceStatus status;
  int? latencyMs;

  AudioDevice({
    required this.id,
    required this.name,
    required this.kind,
    required this.transport,
    required this.status,
    required this.latencyMs,
  });
}
