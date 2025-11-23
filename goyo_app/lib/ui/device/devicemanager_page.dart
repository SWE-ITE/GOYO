import 'package:flutter/material.dart';
import 'package:goyo_app/data/models/device_models.dart';
import 'package:goyo_app/ui/device/widget/deviceinfo.dart';
import 'package:goyo_app/data/services/api_service.dart';
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

  late ApiService _api;
  bool _initialLoading = true;
  bool _scanningWifi = false;
  bool _calibrating = false;
  List<DeviceDto> _devices = const [];
  MicrophoneSetup? _setup;
  bool _iotScanning = false;
  List<DeviceDto> _iotDevices = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _api = context.read<ApiService>();
      _loadDevices();
      _loadSetup();
      _loadDemoIotDevices();
    });
  }

  Future<void> _loadDevices() async {
    setState(() => _initialLoading = true);
    try {
      final devices = await _api.getDevices();
      if (!mounted) return;
      setState(() => _devices = devices);
    } catch (e) {
      _showSnack('디바이스 목록을 불러올 수 없습니다: $e', isError: true);
    } finally {
      if (mounted) setState(() => _initialLoading = false);
    }
  }

  Future<void> _loadSetup() async {
    try {
      final data = await _api.getMicrophoneSetup();
      if (mounted) setState(() => _setup = data);
    } catch (e) {
      _showSnack('마이크 구성을 불러올 수 없습니다: $e', isError: true);
    }
  }

  Future<void> _loadDemoIotDevices() async {
    await Future.delayed(const Duration(milliseconds: 200));
    if (!mounted) return;
    setState(() => _iotDevices = List<DeviceDto>.from(_demoDevices));
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
                    onPressed: _scanningWifi ? null : _scanWifiDevices,
                    icon: _scanningWifi
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.wifi_tethering),
                    label: Text(_scanningWifi ? 'Scanning...' : 'Scan Wi-Fi'),
                  ),
                  IconButton(
                    tooltip: '새로고침',
                    onPressed: _initialLoading
                        ? null
                        : () {
                            _loadDevices();
                            _loadSetup();
                          },
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            if (_setup != null)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Card(
                  child: ListTile(
                    title: const Text('마이크 구성 상태'),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 8),
                        Text('송신 마이크: ${_setup!.sourceMicrophone ?? '미지정'}'),
                        Text('참조 마이크: ${_setup!.referenceMicrophone ?? '미지정'}'),
                        Text('스피커: ${_setup!.speaker ?? '미지정'}'),
                        const SizedBox(height: 4),
                        Text(
                          _setup!.isReady ? '준비 완료' : '구성이 필요합니다',
                          style: TextStyle(
                            color: _setup!.isReady ? cs.primary : cs.error,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    trailing: FilledButton.tonal(
                      onPressed: _calibrating ? null : _calibrateIfPossible,
                      child: _calibrating
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Calibrate'),
                    ),
                  ),
                ),
              ),
            Expanded(
              child: _initialLoading
                  ? const Center(child: CircularProgressIndicator())
                  : ListView(
                      children: [
                        if (_devices.isEmpty)
                          const Padding(
                            padding: EdgeInsets.all(24),
                            child: Center(child: Text('등록된 오디오 디바이스가 없습니다.')),
                          ),
                        if (_devices.isNotEmpty) ..._buildDeviceTiles(cs),

                        const Divider(height: 32),
                        _buildIotDemoSection(cs),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildDeviceTiles(ColorScheme cs) {
    return [
      for (int i = 0; i < _devices.length; i++)
        Column(
          children: [
            ListTile(
              leading: Icon(
                _iconForType(_devices[i].deviceType),
                color: cs.primary,
              ),
              title: Text(
                _devices[i].deviceName,
                style: const TextStyle(fontSize: 18),
              ),
              subtitle: Text(
                _devices[i].isConnected ? 'Connected' : 'Not Connected',
                style: TextStyle(
                  color: _devices[i].isConnected
                      ? cs.primary
                      : cs.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    icon: const Icon(Icons.info_outline),
                    onPressed: () async {
                      final result = await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => DeviceInfo(device: _devices[i]),
                        ),
                      );
                      if (result is Map<String, dynamic> &&
                          result['deletedId'] != null) {
                        _deleteByDeviceId(result['deletedId'] as String);
                      }
                    },
                  ),
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      switch (value) {
                        case 'source':
                          _assignRole(_devices[i], 'microphone_source');
                          break;
                        case 'reference':
                          _assignRole(_devices[i], 'microphone_reference');
                          break;
                        case 'delete':
                          _deleteByDeviceId(_devices[i].deviceId);
                          break;
                      }
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'source', child: Text('송신 마이크로 지정')),
                      PopupMenuItem(
                        value: 'reference',
                        child: Text('참조 마이크로 지정'),
                      ),
                      PopupMenuDivider(),
                      PopupMenuItem(value: 'delete', child: Text('삭제')),
                    ],
                  ),
                ],
              ),
              onTap: () => _showDeviceStatus(_devices[i]),
            ),
            if (i != _devices.length - 1) const Divider(height: 1),
          ],
        ),
    ];
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

  Future<void> _scanWifiDevices() async {
    setState(() => _scanningWifi = true);
    await _scanAndPair();
    if (mounted) setState(() => _scanningWifi = false);
  }

  Future<void> _scanDemoIotDevices() async {
    setState(() => _iotScanning = true);
    try {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return;

      final alreadyAdded = _iotDevices.any(
        (d) => d.deviceId == 'smart-chair-01',
      );
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
          ipAddress: '192.168.0.120',
        ),
      ];

      final selected = await _showDiscoveryDialog(
        available,
        title: 'Wi-Fi 디바이스 연결',
      );
      if (selected == null) {
        _showSnack('스마트 의자 연결을 취소했어요.');
        return;
      }

      await _pairDemoIotDevice(selected);
    } finally {
      if (mounted) setState(() => _iotScanning = false);
    }
  }

  Future<void> _scanAndPair() async {
    try {
      final found = await _api.discoverWifiDevices();

      if (!mounted) return;
      if (found.isEmpty) {
        _showSnack('검색된 디바이스가 없습니다.');
        return;
      }

      final selected = await _showDiscoveryDialog(
        found,
        title: 'Wi-Fi 디바이스 연결',
      );
      if (selected == null) {
        _showSnack('디바이스 연결을 취소했어요.');
        return;
      }

      await _pairDevice(selected);
    } catch (e) {
      _showSnack('디바이스 검색에 실패했습니다: $e', isError: true);
    }
  }

  Future<void> _pairDevice(DiscoveredDevice device) async {
    final navigator = Navigator.of(context, rootNavigator: true);
    final progress = _buildProgressDialog(
      '${device.deviceName} 디바이스와 연결 중입니다...',
    );
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => progress,
    );

    try {
      final paired = await _api.pairDevice(
        PairDeviceRequest(
          deviceId: device.deviceId,
          deviceName: device.deviceName,
          deviceType: device.deviceType,
          connectionType: device.connectionType,
        ),
      );

      if (!mounted) return;
      setState(() {
        final updated = List<DeviceDto>.from(_devices);
        final idx = updated.indexWhere((d) => d.deviceId == paired.deviceId);
        if (idx >= 0) {
          updated[idx] = paired;
        } else {
          updated.add(paired);
        }
        _devices = updated;
      });
      _showSnack('"${device.deviceName}"이(가) 연결되었습니다.');
      await _loadSetup();
    } catch (e) {
      _showSnack('디바이스 연결에 실패했습니다: $e', isError: true);
    } finally {
      if (navigator.canPop()) navigator.pop();
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

  Future<void> _showDeviceStatus(DeviceDto device) async {
    final navigator = Navigator.of(context, rootNavigator: true);
    final progress = _buildProgressDialog('디바이스 상태 확인 중...');
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => progress,
    );

    try {
      final status = await _api.getDeviceStatus(device.deviceId);
      if (!mounted) return;
      setState(() {
        final idx = _devices.indexWhere((d) => d.deviceId == device.deviceId);
        if (idx != -1) {
          final updated = List<DeviceDto>.from(_devices);
          updated[idx] = updated[idx].copyWith(
            isConnected: status.isConnected,
            isCalibrated: status.isCalibrated,
            deviceType: status.deviceType,
          );
          _devices = updated;
        }
      });
      await _loadSetup();
      if (navigator.canPop()) navigator.pop();
      if (!mounted) return;
      showModalBottomSheet<void>(
        context: context,
        builder: (_) {
          return Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  device.deviceName,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text('ID: ${status.deviceId}'),
                Text('타입: ${_deviceTypeLabel(status.deviceType)}'),
                Text('연결 상태: ${status.isConnected ? '연결됨' : '연결 안 됨'}'),
                Text('캘리브레이션: ${status.isCalibrated ? '완료' : '필요'}'),
                if (status.redisStatus != null) ...[
                  const Divider(),
                  Text('상태 메타데이터: ${status.redisStatus}'),
                ],
              ],
            ),
          );
        },
      );
    } catch (e) {
      if (navigator.canPop()) navigator.pop();
      _showSnack('상태 조회에 실패했습니다: $e', isError: true);
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

  Future<void> _assignRole(DeviceDto device, String role) async {
    try {
      final result = await _api.assignMicrophoneRole(
        deviceId: device.deviceId,
        role: role,
      );
      if (!mounted) return;
      setState(() {
        final idx = _devices.indexWhere((d) => d.deviceId == device.deviceId);
        if (idx != -1) {
          final updated = List<DeviceDto>.from(_devices);
          updated[idx] = updated[idx].copyWith(deviceType: result.deviceType);
          _devices = updated;
        }
      });
      await _loadSetup();
      _showSnack(result.message.isEmpty ? '마이크 역할이 변경되었습니다.' : result.message);
    } catch (e) {
      _showSnack('마이크 역할 변경 실패: $e', isError: true);
    }
  }

  Future<void> _calibrateIfPossible() async {
    final source = _firstDeviceOfType('microphone_source');
    final reference = _firstDeviceOfType('microphone_reference');

    if (source == null || reference == null) {
      _showSnack('송신/참조 마이크를 먼저 지정해주세요.', isError: true);
      return;
    }

    setState(() => _calibrating = true);
    try {
      final result = await _api.calibrateDualMicrophones(
        sourceDeviceId: source.deviceId,
        referenceDeviceId: reference.deviceId,
      );
      if (!mounted) return;
      setState(() {
        _devices = _devices
            .map(
              (d) =>
                  (d.deviceId == source.deviceId ||
                      d.deviceId == reference.deviceId)
                  ? d.copyWith(isCalibrated: true)
                  : d,
            )
            .toList();
      });
      await _loadSetup();
      _showSnack(
        '캘리브레이션 완료 (delay: ${result.timeDelay?.toStringAsFixed(3) ?? '-'}초)',
      );
    } catch (e) {
      _showSnack('캘리브레이션 실패: $e', isError: true);
    } finally {
      if (mounted) setState(() => _calibrating = false);
    }
  }

  Future<void> _deleteByDeviceId(String deviceId) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('디바이스 삭제'),
        content: const Text('이 디바이스를 삭제할까요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('삭제'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    try {
      await _api.deleteDevice(deviceId);
      if (!mounted) return;
      setState(() => _devices.removeWhere((d) => d.deviceId == deviceId));
      await _loadSetup();
      _showSnack('디바이스를 삭제했습니다.');
    } catch (e) {
      _showSnack('디바이스 삭제 실패: $e', isError: true);
    }
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

  DeviceDto? _firstDeviceOfType(String type) {
    for (final d in _devices) {
      if (d.deviceType == type) return d;
    }
    return null;
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
