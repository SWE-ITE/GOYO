import 'package:flutter/material.dart';
import 'package:goyo_app/data/models/device_models.dart';
import 'package:goyo_app/ui/device/widget/deviceinfo.dart';

class DeviceManager extends StatefulWidget {
  const DeviceManager({super.key});

  @override
  State<DeviceManager> createState() => _DeviceManagerPageState();
}

class _DeviceManagerPageState extends State<DeviceManager> {
  static const List<DeviceDto> _demoDevices = [
    DeviceDto(
      id: 1,
      userId: 1,
      deviceId: 'fridge-01',
      deviceName: '스마트 냉장고',
      deviceType: 'refrigerator',
      isConnected: true,
      connectionType: 'wifi',
      isCalibrated: true,
    ),
    DeviceDto(
      id: 2,
      userId: 1,
      deviceId: 'tv-01',
      deviceName: '거실 TV',
      deviceType: 'tv',
      isConnected: false,
      connectionType: 'wifi',
      isCalibrated: true,
    ),
    DeviceDto(
      id: 3,
      userId: 1,
      deviceId: 'robot-01',
      deviceName: '로봇 청소기',
      deviceType: 'robot_cleaner',
      isConnected: true,
      connectionType: 'wifi',
      isCalibrated: false,
    ),
  ];

  bool scanning = false;
  bool _initialLoading = true;
  List<DeviceDto> _devices = const [];

  @override
  void initState() {
    super.initState();
    _loadDemoDevices();
  }

  Future<void> _loadDemoDevices() async {
    await Future.delayed(const Duration(milliseconds: 400));
    if (!mounted) return;
    setState(() {
      _devices = List<DeviceDto>.from(_demoDevices);
      _initialLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
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
                        : const Icon(Icons.wifi_tethering),
                    label: Text(scanning ? 'Scanning...' : 'Scan Wi-Fi'),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: _initialLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _devices.isEmpty
                  ? const Center(child: Text('등록된 오디오 디바이스가 없습니다.'))
                  : ListView.separated(
                      itemCount: _devices.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, i) {
                        final d = _devices[i];
                        final isConn = d.isConnected;

                        return ListTile(
                          leading: Icon(
                            _iconForType(d.deviceType),
                            color: cs.primary,
                          ),
                          title: Text(
                            d.deviceName,
                            style: const TextStyle(fontSize: 18),
                          ),
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
                                  () =>
                                      _devices.removeWhere((x) => x.id == d.id),
                                );
                                _showSnack('Deleted "${d.deviceName}"');
                              }
                            },
                          ),
                          onTap: () => _handleDeviceTap(d),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _scanDevices() async {
    setState(() => scanning = true);
    try {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return;

      final alreadyAdded = _devices.any((d) => d.deviceId == 'smart-chair-01');
      if (alreadyAdded) {
        _showSnack('스마트 의자가 이미 연결되어 있습니다.');
        return;
      }

      final available = [
        const DiscoveredDevice(
          deviceId: 'smart-chair-01',
          deviceName: 'Smart Chair',
          deviceType: 'smart_chair',
          connectionType: 'wifi',
          signalStrength: -42,
          ipAddress: '192.168.0.120',
        ),
      ];

      final selected = await _showDiscoveryDialog(available);
      if (selected == null) {
        _showSnack('스마트 의자 연결을 취소했어요.');
        return;
      }

      await _pairDevice(selected);
    } finally {
      if (mounted) setState(() => scanning = false);
    }
  }

  Future<void> _pairDevice(DiscoveredDevice device) async {
    final navigator = Navigator.of(context, rootNavigator: true);
    final progress = _buildProgressDialog('Wi-Fi 디바이스와 연결 중입니다...');
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => progress,
    );

    await Future.delayed(const Duration(milliseconds: 800));
    if (!mounted) return;
    setState(() {
      final nextId = _nextDeviceId();
      final paired = DeviceDto(
        id: nextId,
        userId: 1,
        deviceId: device.deviceId,
        deviceName: device.deviceName,
        deviceType: device.deviceType,
        isConnected: true,
        connectionType: device.connectionType,
        isCalibrated: true,
      );
      _devices = [..._devices, paired];
    });
    _showSnack('"${device.deviceName}"이(가) 연결되었습니다.');
    if (navigator.canPop()) navigator.pop();
  }

  Future<void> _handleDeviceTap(DeviceDto device) async {
    final wantConnect = !device.isConnected;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(wantConnect ? '디바이스 연결' : '디바이스 연결 해제'),
        content: Text(
          wantConnect
              ? 'Wi-Fi로 "${device.deviceName}" 기기를 연결할까요?'
              : '"${device.deviceName}" 기기의 연결을 해제할까요?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(wantConnect ? '연결' : '해제'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() {
      final idx = _devices.indexWhere((d) => d.id == device.id);
      if (idx != -1) {
        final updatedList = List<DeviceDto>.from(_devices);
        updatedList[idx] = device.copyWith(isConnected: wantConnect);
        _devices = updatedList;
      }
    });
    _showSnack(
      wantConnect
          ? '"${device.deviceName}"이(가) 연결되었습니다.'
          : '"${device.deviceName}" 연결을 해제했습니다.',
    );
  }

  Future<DiscoveredDevice?> _showDiscoveryDialog(
    List<DiscoveredDevice> found,
  ) async {
    String? selectedId = found.first.deviceId;
    return showDialog<DiscoveredDevice>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: const Text('Wi-Fi 디바이스 연결'),
              content: SizedBox(
                width: 360,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Align(
                        alignment: Alignment.centerLeft,
                        child: Text('연결할 디바이스를 선택하세요.'),
                      ),
                      const SizedBox(height: 12),
                      for (final device in found)
                        RadioListTile<String>(
                          value: device.deviceId,
                          groupValue: selectedId,
                          onChanged: (value) =>
                              setState(() => selectedId = value),
                          title: Text(device.deviceName),
                          subtitle: Text(_buildDiscoverySubtitle(device)),
                        ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('취소'),
                ),
                FilledButton(
                  onPressed: selectedId == null
                      ? null
                      : () {
                          final target = found.firstWhere(
                            (d) => d.deviceId == selectedId,
                          );
                          Navigator.pop(context, target);
                        },
                  child: const Text('연결'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  String _buildDiscoverySubtitle(DiscoveredDevice device) {
    final parts = <String>[_deviceTypeLabel(device.deviceType)];
    if (device.signalStrength != null) {
      parts.add('${device.signalStrength} dBm');
    }
    final ip = device.ipAddress;
    if (ip != null && ip.isNotEmpty) {
      parts.add(ip);
    }
    return parts.join(' • ');
  }

  int _nextDeviceId() {
    if (_devices.isEmpty) return 1;
    int maxId = _devices.first.id;
    for (final d in _devices.skip(1)) {
      if (d.id > maxId) maxId = d.id;
    }
    return maxId + 1;
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

  AlertDialog _buildProgressDialog(String message) {
    return AlertDialog(
      content: SizedBox(
        height: 96,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(message),
          ],
        ),
      ),
    );
  }

  void _showSnack(String message, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Theme.of(context).colorScheme.error : null,
      ),
    );
  }
}
