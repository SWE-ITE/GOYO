class DeviceDto {
  final int id;
  final int userId;
  final String deviceId;
  final String deviceName;
  final String deviceType;
  final bool isConnected;
  final String connectionType;
  final bool isCalibrated;

  const DeviceDto({
    required this.id,
    required this.userId,
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.isConnected,
    required this.connectionType,
    required this.isCalibrated,
  });

  factory DeviceDto.fromJson(Map<String, dynamic> json) {
    return DeviceDto(
      id: json['id'] as int,
      userId: json['user_id'] as int? ?? 0,
      deviceId: json['device_id'] as String? ?? '',
      deviceName: json['device_name'] as String? ?? 'Unknown device',
      deviceType: json['device_type'] as String? ?? 'speaker',
      isConnected: json['is_connected'] as bool? ?? false,
      connectionType: json['connection_type'] as String? ?? 'wifi',
      isCalibrated: json['is_calibrated'] as bool? ?? false,
    );
  }
  DeviceDto copyWith({
    int? id,
    int? userId,
    String? deviceId,
    String? deviceName,
    String? deviceType,
    bool? isConnected,
    String? connectionType,
    bool? isCalibrated,
  }) {
    return DeviceDto(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      deviceId: deviceId ?? this.deviceId,
      deviceName: deviceName ?? this.deviceName,
      deviceType: deviceType ?? this.deviceType,
      isConnected: isConnected ?? this.isConnected,
      connectionType: connectionType ?? this.connectionType,
      isCalibrated: isCalibrated ?? this.isCalibrated,
    );
  }
}

class DiscoveredDevice {
  final String deviceId;
  final String deviceName;
  final String deviceType;
  final String connectionType;
  final int? signalStrength;
  final String? ipAddress;

  const DiscoveredDevice({
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.connectionType,
    this.signalStrength,
    this.ipAddress,
  });

  factory DiscoveredDevice.fromJson(Map<String, dynamic> json) {
    return DiscoveredDevice(
      deviceId: json['device_id'] as String? ?? '',
      deviceName: json['device_name'] as String? ?? 'Unknown',
      deviceType: json['device_type'] as String? ?? 'speaker',
      connectionType: json['connection_type'] as String? ?? 'wifi',
      signalStrength: json['signal_strength'] as int?,
      ipAddress: json['ip_address'] as String?,
    );
  }
}

class PairDeviceRequest {
  final String deviceId;
  final String deviceName;
  final String deviceType;
  final String connectionType;

  const PairDeviceRequest({
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.connectionType,
  });

  Map<String, dynamic> toJson() => {
    'device_id': deviceId,
    'device_name': deviceName,
    'device_type': deviceType,
    'connection_type': connectionType,
  };
}
