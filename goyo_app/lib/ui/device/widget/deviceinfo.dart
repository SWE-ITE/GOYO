import 'package:flutter/material.dart';
import 'package:goyo_app/data/models/device_models.dart';
import 'package:goyo_app/data/services/api_service.dart';
import 'package:provider/provider.dart';

class DeviceInfo extends StatelessWidget {
  final DeviceDto device;
  const DeviceInfo({super.key, required this.device});

  Future<void> _confirmDelete(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete device'),
        content: Text(
          'Delete "${device.deviceName}"? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (ok == true) {
      Navigator.pop(context, {'deletedId': device.deviceId});
    }
  }

  Future<void> _checkStatus(BuildContext context) async {
    final api = context.read<ApiService>();
    final navigator = Navigator.of(context, rootNavigator: true);
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => const AlertDialog(
        content: SizedBox(
          height: 96,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('디바이스 상태를 확인하고 있어요...'),
            ],
          ),
        ),
      ),
    );

    try {
      final status = await api.getDeviceStatus(device.deviceId);
      if (navigator.canPop()) navigator.pop();
      if (context.mounted) {
        showModalBottomSheet<void>(
          context: context,
          builder: (_) => Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(device.deviceName,
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text('연결: ${status.isConnected ? 'ON' : 'OFF'}'),
                Text('캘리브레이션: ${status.isCalibrated ? '완료' : '필요'}'),
                Text('유형: ${status.deviceType}'),
                if (status.redisStatus != null)
                  Text('메타: ${status.redisStatus}'),
              ],
            ),
          ),
        );
      }
    } catch (e) {
      if (navigator.canPop()) navigator.pop();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('상태 확인 실패: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isConn = device.isConnected;
    final icon = _iconForType(device.deviceType);
    final typeLabel = _deviceTypeLabel(device.deviceType);

    return Scaffold(
      appBar: AppBar(title: const Text('Device Info')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            leading: CircleAvatar(
              backgroundColor: cs.primary.withOpacity(.12),
              child: Icon(icon, color: cs.primary),
            ),
            title: Text(
              device.deviceName,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
            ),
            subtitle: Text(isConn ? 'Connected' : 'Not Connected'),
          ),
          const Divider(),
          ListTile(
            title: const Text('Device ID'),
            subtitle: Text(
              device.deviceId.isEmpty ? '#${device.id}' : device.deviceId,
            ),
          ),
          ListTile(title: const Text('Type'), subtitle: Text(typeLabel)),
          ListTile(
            title: const Text('Connection'),
            subtitle: Text(device.connectionType.toUpperCase()),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: FilledButton(
                   onPressed: () => _checkStatus(context),
                  child: const Text('Check status'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.tonal(
                  style: FilledButton.styleFrom(foregroundColor: cs.error),
                  onPressed: () => _confirmDelete(context),
                  child: const Text('Delete'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

IconData _iconForType(String type) {
  switch (type) {
    case 'microphone_source':
      return Icons.mic_outlined;
    case 'microphone_reference':
      return Icons.mic_external_on_outlined;
    case 'speaker':
      return Icons.speaker;
    case 'refrigerator':
      return Icons.kitchen;
    case 'tv':
      return Icons.tv;
    case 'robot_cleaner':
      return Icons.cleaning_services;
    case 'smart_chair':
      return Icons.event_seat;
    default:
      return Icons.devices_other;
  }
}

String _deviceTypeLabel(String type) {
  switch (type) {
    case 'microphone_source':
      return '송신 마이크';
    case 'microphone_reference':
      return '참조 마이크';
    case 'speaker':
      return '스피커';
    case 'refrigerator':
      return '냉장고';
    case 'tv':
      return 'TV';
    case 'robot_cleaner':
      return '로봇 청소기';
    case 'smart_chair':
      return '스마트 의자';
    default:
      return type;
  }
}
