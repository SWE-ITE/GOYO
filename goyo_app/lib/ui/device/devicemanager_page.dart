import 'package:flutter/material.dart';
import 'package:goyo_app/data/models/device_models.dart';
import 'package:goyo_app/data/services/api_service.dart';
import 'package:goyo_app/ui/device/widget/deviceinfo.dart';
import 'package:provider/provider.dart';

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

  bool _iotScanning = false;
  List<DeviceDto> _iotDevices = const [];
  bool _smartChairScanning = false;
  bool _loadingSmartChairs = false;
  bool _loadingSetup = false;
  bool _smartChairReady = false;
  Map<String, dynamic>? _smartChairSetup;
  List<DeviceDto> _smartChairs = const [];

  @override
  void initState() {
    super.initState();
    _iotDevices = List<DeviceDto>.from(_demoDevices);
    _loadSmartChairs();
  }

  Widget _buildSmartChairSetupInfo(ColorScheme cs) {
    final setup = _smartChairSetup;
    final goyo = setup != null && setup['goyo_device'] is Map<String, dynamic>
        ? setup['goyo_device'] as Map<String, dynamic>
        : null;
    final statusText = _smartChairReady ? '준비 완료' : '설정 필요';
    final ip = goyo?['ip_address'] as String?;

    return Row(
      children: [
        Chip(
          backgroundColor:
              _smartChairReady ? cs.primaryContainer : cs.surfaceVariant,
          label: Text(
            statusText,
            style: TextStyle(
              color: _smartChairReady ? cs.onPrimaryContainer : cs.onSurface,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        const SizedBox(width: 8),
        if (ip != null && ip.isNotEmpty)
          Text(
            'IP: $ip',
            style: TextStyle(color: cs.onSurfaceVariant),
          )
        else if (setup != null)
          Text(
            '네트워크 정보 없음',
            style: TextStyle(color: cs.onSurfaceVariant),
          ),
      ],
    );
  }

  Future<void> _loadSmartChairs() async {
    await Future.wait([
      _fetchSmartChairs(),
      _refreshSmartChairSetup(),
    ]);
  }

  Future<void> _fetchSmartChairs() async {
    setState(() => _loadingSmartChairs = true);
    try {
      final api = context.read<ApiService>();
      final devices = await api.getDevices();
      final chairs = devices
          .where((d) => _isSmartChairType(d.deviceType))
          .map(_normalizeSmartChair)
          .toList();
      if (!mounted) return;
      setState(() => _smartChairs = chairs);
    } catch (e) {
      _showSnack('스마트 의자 목록을 불러오지 못했어요: $e', isError: true);
    } finally {
      if (mounted) setState(() => _loadingSmartChairs = false);
    }
  }

  Future<void> _refreshSmartChairSetup() async {
    setState(() => _loadingSetup = true);
    try {
      final api = context.read<ApiService>();
      final setup = await api.getDeviceSetup();
      if (!mounted) return;
      setState(() {
        _smartChairSetup = setup;
        _smartChairReady = setup['is_ready'] == true;
      });
    } catch (e) {
      _showSnack('의자 구성 정보를 가져오지 못했어요: $e', isError: true);
    } finally {
      if (mounted) setState(() => _loadingSetup = false);
    }
  }

  DeviceDto _normalizeSmartChair(DeviceDto device) {
    final normalizedType =
        _isSmartChairType(device.deviceType) ? 'smart_chair' : device.deviceType;
    return device.copyWith(deviceType: normalizedType);
  }

  bool _isSmartChairType(String type) {
    return type == 'smart_chair' || type == 'goyo_device';
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 12),
            _buildSmartChairSection(cs),
            const Divider(height: 32),
            _buildIotDemoSection(cs),
          ],
        ),
      ),
    );
  }

  Widget _buildIotDemoSection(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: Card(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: cs.outlineVariant),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    '기존 IoT 디바이스 (데모)',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  TextButton.icon(
                    onPressed: _iotScanning ? null : _scanDemoIotDevices,
                    icon: _iotScanning
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.wifi_tethering),
                    label: Text(_iotScanning ? 'Scanning...' : 'Scan Wi-Fi'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (_iotDevices.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text('등록된 IoT 기기가 없습니다.'),
                )
              else
                Column(
                  children: [
                    for (int i = 0; i < _iotDevices.length; i++) ...[
                      ListTile(
                        leading: Icon(
                          _iconForType(_iotDevices[i].deviceType),
                          color: cs.primary,
                        ),
                        title: Text(_iotDevices[i].deviceName),
                        subtitle: Text(
                          _iotDevices[i].isConnected
                              ? 'Connected'
                              : 'Not Connected',
                          style: TextStyle(
                            color: _iotDevices[i].isConnected
                                ? cs.primary
                                : cs.onSurfaceVariant,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.info_outline),
                          onPressed: () async {
                            final res = await Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    DeviceInfo(device: _iotDevices[i]),
                              ),
                            );
                            if (res is Map &&
                                res['deletedId'] == _iotDevices[i].deviceId) {
                              setState(
                                () => _iotDevices.removeWhere(
                                  (x) => x.deviceId == _iotDevices[i].deviceId,
                                ),
                              );
                              _showSnack(
                                'Deleted "${_iotDevices[i].deviceName}"',
                              );
                            }
                          },
                        ),
                        onTap: () => _handleIotDeviceTap(_iotDevices[i]),
                      ),
                      if (i != _iotDevices.length - 1)
                        Divider(height: 1, color: cs.outlineVariant),
                    ],
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSmartChairSection(ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: Card(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: cs.outlineVariant),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    '등록된 스마트 의자',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  TextButton.icon(
                    onPressed: (_smartChairScanning || _loadingSmartChairs)
                        ? null
                        : _scanSmartChairs,
                    icon: _smartChairScanning
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.wifi_tethering),
                    label: Text(
                      _smartChairScanning ? 'Scanning...' : 'Scan Wi-Fi',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              if (_loadingSetup)
                const LinearProgressIndicator(minHeight: 2)
              else
                _buildSmartChairSetupInfo(cs),
              const SizedBox(height: 12),
              if (_loadingSmartChairs)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_smartChairs.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text('등록된 스마트 의자가 없습니다.'),
                )
              else
                Column(
                  children: [
                    for (int i = 0; i < _smartChairs.length; i++) ...[
                      ListTile(
                        leading: Icon(
                          _iconForType(_smartChairs[i].deviceType),
                          color: cs.primary,
                        ),
                        title: Text(_smartChairs[i].deviceName),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _smartChairs[i].isConnected
                                  ? 'Connected'
                                  : 'Not Connected',
                              style: TextStyle(
                                color: _smartChairs[i].isConnected
                                    ? cs.primary
                                    : cs.onSurfaceVariant,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            if (_smartChairs[i].ipAddress?.isNotEmpty == true)
                              Text(
                                'IP: ${_smartChairs[i].ipAddress}',
                                style: TextStyle(color: cs.onSurfaceVariant),
                              ),
                          ],
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _handleSmartChairTap(_smartChairs[i]),
                      ),
                      if (i != _smartChairs.length - 1)
                        Divider(height: 1, color: cs.outlineVariant),
                    ],
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _scanDemoIotDevices() async {
    setState(() => _iotScanning = true);
    try {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return;

      final available = <DiscoveredDevice>[];
      if (available.isEmpty) {
        _showSnack('검색된 IoT 기기가 없습니다.');
        return;
      }

      final selected = await _showDiscoveryDialog(
        available,
        title: 'Wi-Fi 디바이스 연결',
      );
      if (selected == null) {
        _showSnack('IoT 디바이스 연결을 취소했어요.');
        return;
      }
      await _pairDemoIotDevice(selected);
    } finally {
      if (mounted) setState(() => _iotScanning = false);
    }
  }

  Future<void> _scanSmartChairs() async {
    setState(() => _smartChairScanning = true);
    try {
      final api = context.read<ApiService>();
      final available = await api.discoverWifiDevices();
      final chairs =
          available.where((d) => _isSmartChairType(d.deviceType)).toList();
      if (chairs.isEmpty) {
        _showSnack('검색된 스마트 의자가 없습니다.');
        return;
      }

      final selected = await _showDiscoveryDialog(
        chairs,
        title: '스마트 의자 연결',
      );
      if (selected == null) {
        _showSnack('스마트 의자 연결을 취소했어요.');
        return;
      }

      await _pairSmartChair(selected);
    } catch (e) {
      _showSnack('스마트 의자 검색에 실패했어요: $e', isError: true);
    } finally {
      if (mounted) setState(() => _smartChairScanning = false);
    }
  }

  Future<void> _pairDemoIotDevice(DiscoveredDevice device) async {
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
      final nextId = _nextIotDeviceId();
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
      _iotDevices = [..._iotDevices, paired];
    });
    _showSnack('"${device.deviceName}"이(가) 연결되었습니다.');
    if (navigator.canPop()) navigator.pop();
  }

  Future<void> _pairSmartChair(DiscoveredDevice device) async {
    final navigator = Navigator.of(context, rootNavigator: true);
    final progress = _buildProgressDialog('스마트 의자와 연결 중입니다...');
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => progress,
    );

    try {
      final api = context.read<ApiService>();
      final paired = await api.pairDevice(
        PairDeviceRequest(
          deviceId: device.deviceId,
          deviceName: device.deviceName,
          deviceType:
              _isSmartChairType(device.deviceType) ? 'goyo_device' : device.deviceType,
          connectionType: device.connectionType,
          ipAddress: device.ipAddress ?? '',
        ),
      );
      if (!mounted) return;
      setState(() {
        final normalized = _normalizeSmartChair(paired);
        _smartChairs = [
          ..._smartChairs.where((d) => d.deviceId != normalized.deviceId),
          normalized,
        ];
      });
      await _refreshSmartChairSetup();
      _showSnack('"${device.deviceName}"이(가) 연결되었습니다.');
    } catch (e) {
      _showSnack('스마트 의자 페어링 실패: $e', isError: true);
    } finally {
      if (navigator.canPop()) navigator.pop();
    }
  }

  Future<void> _handleIotDeviceTap(DeviceDto device) async {
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
      final idx = _iotDevices.indexWhere((d) => d.id == device.id);
      if (idx != -1) {
        final updatedList = List<DeviceDto>.from(_iotDevices);
        updatedList[idx] = device.copyWith(isConnected: wantConnect);
        _iotDevices = updatedList;
      }
    });
    _showSnack(
      wantConnect
          ? '"${device.deviceName}"이(가) 연결되었습니다.'
          : '"${device.deviceName}" 연결을 해제했습니다.',
    );
  }

  Future<void> _handleSmartChairTap(DeviceDto device) async {
    final res = await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DeviceInfo(device: device),
      ),
    );

    if (res is Map && res['deletedId'] == device.deviceId) {
      setState(() {
        _smartChairs =
            _smartChairs.where((d) => d.deviceId != device.deviceId).toList();
      });
      await _refreshSmartChairSetup();
      return;
    }

    await _fetchSmartChairs();
    await _refreshSmartChairSetup();
  }

  Future<DiscoveredDevice?> _showDiscoveryDialog(
    List<DiscoveredDevice> found, {
    String title = '디바이스 연결',
  }) async {
    String? selectedId = found.first.deviceId;
    return showDialog<DiscoveredDevice>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text(title),
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

  int _nextIotDeviceId() {
    if (_iotDevices.isEmpty) return 1;
    int maxId = _iotDevices.first.id;
    for (final d in _iotDevices.skip(1)) {
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
      case 'goyo_device':
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
      case 'goyo_device':
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
