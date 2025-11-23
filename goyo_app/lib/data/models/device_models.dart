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

class DeviceStatus {
  final String deviceId;
  final String deviceName;
  final String deviceType;
  final bool isConnected;
  final bool isCalibrated;
  final Map<String, dynamic>? redisStatus;

  const DeviceStatus({
    required this.deviceId,
    required this.deviceName,
    required this.deviceType,
    required this.isConnected,
    required this.isCalibrated,
    this.redisStatus,
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
    );
  }
}

class MicrophoneSetup {
  final String? sourceMicrophone;
  final String? referenceMicrophone;
  final String? speaker;
  final bool isReady;

  const MicrophoneSetup({
    required this.sourceMicrophone,
    required this.referenceMicrophone,
    required this.speaker,
    required this.isReady,
  });

  factory MicrophoneSetup.fromJson(Map<String, dynamic> json) {
    return MicrophoneSetup(
      sourceMicrophone: json['source_microphone'] as String?,
      referenceMicrophone: json['reference_microphone'] as String?,
      speaker: json['speaker'] as String?,
      isReady: json['is_ready'] as bool? ?? false,
    );
  }
}

class CalibrationResult {
  final double? timeDelay;
  final List<double> frequencyResponse;
  final List<double> spatialTransferFunction;
  final String? calibratedAt;

  const CalibrationResult({
    this.timeDelay,
    this.frequencyResponse = const [],
    this.spatialTransferFunction = const [],
    this.calibratedAt,
  });

  factory CalibrationResult.fromJson(Map<String, dynamic> json) {
    List<double> _parseList(dynamic data) {
      if (data is List) {
        return data
            .whereType<num>()
            .map((e) => e.toDouble())
            .toList(growable: false);
      }
      return const [];
    }

    return CalibrationResult(
      timeDelay: (json['time_delay'] as num?)?.toDouble(),
      frequencyResponse: _parseList(json['frequency_response']),
      spatialTransferFunction: _parseList(json['spatial_transfer_function']),
      calibratedAt: json['calibrated_at'] as String?,
    );
  }
}

class RoleAssignmentResult {
  final String message;
  final String deviceId;
  final String deviceType;

  const RoleAssignmentResult({
    required this.message,
    required this.deviceId,
    required this.deviceType,
  });

  factory RoleAssignmentResult.fromJson(Map<String, dynamic> json) {
    return RoleAssignmentResult(
      message: json['message'] as String? ?? '',
      deviceId: json['device_id'] as String? ?? '',
      deviceType: json['device_type'] as String? ?? '',
    );
  }
}
