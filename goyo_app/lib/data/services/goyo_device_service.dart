import 'dart:async';
import 'dart:convert';

import 'package:goyo_app/data/models/device_models.dart';
import 'package:http/http.dart' as http;
import 'package:multicast_dns/multicast_dns.dart';

class GoyoDeviceService {
  const GoyoDeviceService();

  Future<List<DiscoveredDevice>> discoverSmartChairs({
    Duration discoveryTimeout = const Duration(seconds: 5),
  }) async {
    final client = MDnsClient();
    final devices = <String, DiscoveredDevice>{};

    try {
      await client.start();

      final ptrRecords = client
          .lookup<PtrResourceRecord>(
            ResourceRecordQuery.serverPointer('_goyo._tcp.local'),
          )
          .timeout(discoveryTimeout);

      await for (final ptr in ptrRecords) {
        final srvRecords = client
            .lookup<SrvResourceRecord>(
              ResourceRecordQuery.service(ptr.domainName),
            )
            .timeout(const Duration(seconds: 2));

        await for (final srv in srvRecords) {
          final txtRecords = await _readTxtRecords(client, ptr.domainName);

          final ipRecords = client
              .lookup<IPAddressResourceRecord>(
                ResourceRecordQuery.addressIPv4(srv.target),
              )
              .timeout(const Duration(seconds: 2));

          await for (final ip in ipRecords) {
            final deviceId = ptr.domainName.split('.').first;
            devices[deviceId] = DiscoveredDevice(
              deviceId: deviceId,
              deviceName: txtRecords['device_name'] ?? 'GOYO Device',
              deviceType: 'goyo_device',
              connectionType: 'wifi',
              ipAddress: ip.address.address,
              port: srv.port,
            );
          }
        }
      }
    } on TimeoutException {
      // 검색 시간 초과 시 발견된 장치까지만 반환
    } finally {
      try {
        client.stop();
      } catch (_) {}
    }

    return devices.values.toList();
  }

  Future<void> configureDevice({
    required DiscoveredDevice device,
    required int userId,
    required String mqttBrokerHost,
    int mqttBrokerPort = 1883,
    String mqttUsername = 'goyo_backend',
    String mqttPassword = '',
    int fallbackConfigurationPort = 5000,
  }) async {
    final ip = device.ipAddress;
    if (ip == null || ip.isEmpty) {
      throw ArgumentError('Device IP is required for configuration');
    }
    final port = device.port ?? fallbackConfigurationPort;
    final uri = Uri.parse('http://$ip:$port/configure');

    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'mqtt_broker_host': mqttBrokerHost,
        'mqtt_broker_port': mqttBrokerPort,
        'mqtt_username': mqttUsername,
        'mqtt_password': mqttPassword,
        'user_id': userId.toString(),
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('MQTT 설정 전달 실패: ${response.body}');
    }
  }

  Future<Map<String, String>> _readTxtRecords(
    MDnsClient client,
    String domain,
  ) async {
    final records = <String, String>{};
    try {
      final stream = client
          .lookup<TxtResourceRecord>(ResourceRecordQuery.text(domain))
          .timeout(const Duration(seconds: 2));

      await for (final txt in stream) {
        // txt.text 는 String 하나이므로, 구분자 기준으로 잘라서 사용
        for (final entry in txt.text.split('\n')) {
          if (entry.isEmpty) continue;

          final idx = entry.indexOf('=');
          if (idx > 0 && idx < entry.length - 1) {
            final key = entry.substring(0, idx);
            final value = entry.substring(idx + 1);
            records[key] = value;
          }
        }
      }
    } on TimeoutException {
      // TXT 레코드가 없으면 무시
    }
    return records;
  }
}
