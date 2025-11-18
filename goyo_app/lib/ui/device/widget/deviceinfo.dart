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
    final isMic = device.deviceType.toLowerCase().contains('mic');

    return Scaffold(
      appBar: AppBar(title: const Text('Device Info')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            leading: CircleAvatar(
              backgroundColor: cs.primary.withOpacity(.12),
              child: Icon(
                isMic ? Icons.mic : Icons.speaker_outlined,
                color: cs.primary,
              ),
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
          ListTile(
            title: const Text('Type'),
            subtitle: Text(isMic ? 'Microphone' : 'Speaker'),
          ),
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
