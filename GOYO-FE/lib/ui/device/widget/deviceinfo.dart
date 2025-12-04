import 'package:flutter/material.dart';
import 'package:goyo_app/data/models/device_models.dart';
import 'package:goyo_app/data/services/api_service.dart';
import 'package:provider/provider.dart';

class DeviceInfo extends StatefulWidget {
  final DeviceDto device;
  const DeviceInfo({super.key, required this.device});

  @override
  State<DeviceInfo> createState() => _DeviceInfoState();
}

class _DeviceInfoState extends State<DeviceInfo> {
  Future<void> _confirmDelete(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete device'),
        content: Text(
          'Delete "${widget.device.deviceName}"? This action cannot be undone.',
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

    if (ok != true) return;

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
              Text('디바이스를 삭제하는 중이에요...'),
            ],
          ),
        ),
      ),
    );

    try {
      final api = context.read<ApiService>();
      await api.deleteDevice(widget.device.deviceId);
      if (navigator.canPop()) navigator.pop();
      if (context.mounted) {
        Navigator.pop(context, {'deletedId': widget.device.deviceId});
      }
    } catch (e) {
      if (navigator.canPop()) navigator.pop();
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('삭제에 실패했어요: $e')));
      }
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
      final status = await api.getDeviceStatus(widget.device.deviceId);
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
                Text(
                  widget.device.deviceName,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text('연결: ${status.isConnected ? 'ON' : 'OFF'}'),
                Text('캘리브레이션: ${status.isCalibrated ? '완료' : '필요'}'),
                Text('유형: ${status.deviceType}'),
                if (status.ipAddress?.isNotEmpty == true)
                  Text('IP: ${status.ipAddress}'),
                if (status.components != null)
                  Text('구성 요소: ${status.components}'),
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
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('상태 확인 실패: $e')));
      }
    }
  }

  Future<void> _calibrateDevice(BuildContext context) async {
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
              Text('캘리브레이션을 진행 중이에요...'),
            ],
          ),
        ),
      ),
    );

    try {
      final result = await api.calibrateDevice(widget.device.deviceId);
      if (navigator.canPop()) navigator.pop();
      if (context.mounted) {
        final message = result['message'] ?? '완료되었습니다.';
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('캘리브레이션 완료: $message')));
      }
    } catch (e) {
      if (navigator.canPop()) navigator.pop();
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('캘리브레이션 실패: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isConn = widget.device.isConnected;
    final icon = _iconForType(widget.device.deviceType);
    final typeLabel = _deviceTypeLabel(widget.device.deviceType);

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
              widget.device.deviceName,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
            ),
            subtitle: Text(isConn ? 'Connected' : 'Connected'),
          ),
          const Divider(),
          ListTile(
            title: const Text('Device ID'),
            subtitle: Text(
              widget.device.deviceId.isEmpty
                  ? '#${widget.device.id}'
                  : widget.device.deviceId,
            ),
          ),
          ListTile(title: const Text('Type'), subtitle: Text(typeLabel)),
          ListTile(
            title: const Text('Connection'),
            subtitle: Text(widget.device.connectionType.toUpperCase()),
          ),
          ListTile(
            title: const Text('IP Address'),
            subtitle: Text(
              widget.device.ipAddress?.isNotEmpty == true
                  ? widget.device.ipAddress!
                  : 'Not available',
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              SizedBox(
                width: 160,
                child: FilledButton(
                  onPressed: () => _checkStatus(context),
                  child: const Text('Check status'),
                ),
              ),
              SizedBox(
                width: 160,
                child: FilledButton.tonal(
                  onPressed: () => _calibrateDevice(context),
                  child: const Text('Calibrate'),
                ),
              ),
              SizedBox(
                width: 160,
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
    case 'goyo_device':
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
    case 'goyo_device':
    case 'smart_chair':
      return '스마트 의자';
    default:
      return type;
  }
}
