import 'package:flutter/material.dart';
import 'package:goyo_app/data/models/device_models.dart';

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
      // 결과에 삭제된 id를 담아서 반환
      Navigator.pop(context, {'deletedId': device.id});
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
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          isConn ? 'Demo: Disconnect' : 'Demo: Connect',
                        ),
                      ),
                    );
                  },
                  child: Text(isConn ? 'Disconnect' : 'Connect'),
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
