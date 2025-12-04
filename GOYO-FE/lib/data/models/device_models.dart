class DeviceDto {
  final int id;
  final int userId;
  final String deviceId;
  final String deviceName;
  final String deviceType;
  final bool isConnected;
  final String connectionType;
  final bool isCalibrated;
  final String? ipAddress;
  final DateTime? createdAt;

  const DeviceDto({
    required this.id,
    required this.userId,
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.isConnected,
    required this.connectionType,
    required this.isCalibrated,
    this.ipAddress,
    this.createdAt,
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
      ipAddress: json['ip_address'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
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
    String? ipAddress,
    DateTime? createdAt,
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
      ipAddress: ipAddress ?? this.ipAddress,
      createdAt: createdAt ?? this.createdAt,
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
  final int? port;

  const DiscoveredDevice({
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.connectionType,
    this.signalStrength,
    this.ipAddress,
    this.port,
  });

  factory DiscoveredDevice.fromJson(Map<String, dynamic> json) {
    return DiscoveredDevice(
      deviceId: json['device_id'] as String? ?? '',
      deviceName: json['device_name'] as String? ?? 'Unknown',
      deviceType: json['device_type'] as String? ?? 'speaker',
      connectionType: json['connection_type'] as String? ?? 'wifi',
      signalStrength: json['signal_strength'] as int?,
      ipAddress: json['ip_address'] as String?,
      port: json['port'] as int?,
    );
  }
}

class PairDeviceRequest {
  final String deviceId;
  final String deviceName;
  final String deviceType;
  final String connectionType;
  final String ipAddress;

  const PairDeviceRequest({
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.connectionType,
    required this.ipAddress,
  });

  Map<String, dynamic> toJson() => {
    'device_id': deviceId,
    'device_name': deviceName,
    'device_type': deviceType,
    'connection_type': connectionType,
    'ip_address': ipAddress,
  };
}

class DeviceStatus {
  final String deviceId;
  final String deviceName;
  final String deviceType;
  final bool isConnected;
  final bool isCalibrated;
  final Map<String, dynamic>? redisStatus;
  final String? ipAddress;
  final Map<String, dynamic>? components;
  final DateTime? lastSeen;

  const DeviceStatus({
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.isConnected,
    required this.isCalibrated,
    this.redisStatus,
    this.ipAddress,
    this.components,
    this.lastSeen,
  });

  factory DeviceStatus.fromJson(Map<String, dynamic> json) {
    final redis = json['redis_status'];
    return DeviceStatus(
      deviceId: json['device_id'] as String? ?? '',
      deviceName: json['device_name'] as String? ?? '',
      deviceType: json['device_type'] as String? ?? 'unknown',
      isConnected: json['is_connected'] as bool? ?? false,
      isCalibrated: json['is_calibrated'] as bool? ?? false,
      redisStatus: redis is Map<String, dynamic> ? redis : null,
      ipAddress: json['ip_address'] as String?,
      components:
          json['components'] is Map<String, dynamic> ? json['components'] : null,
      lastSeen: json['last_seen'] != null
          ? DateTime.tryParse(json['last_seen'] as String)
          : null,
    );
  }
}
