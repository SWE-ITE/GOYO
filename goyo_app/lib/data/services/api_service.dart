import 'dart:developer' as dev;
import 'package:dio/dio.dart';
import 'package:goyo_app/core/config/env.dart';
import 'package:goyo_app/core/auth/token_manager.dart';
import 'package:goyo_app/features/auth/auth_provider.dart';
import 'package:goyo_app/data/models/device_models.dart';

class ApiService {
  ApiService({Dio? dio})
    : _dio =
          dio ??
          Dio(
            BaseOptions(
              baseUrl: Env.baseUrl,
              connectTimeout: const Duration(seconds: 10),
              receiveTimeout: const Duration(seconds: 10),
              headers: {'Content-Type': 'application/json'},
            ),
          ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (o, h) async {
          final t = await TokenManager.getToken();
          if (t != null && t.isNotEmpty) {
            o.headers['Authorization'] = 'Bearer $t';
          }
          dev.log(
            '➡️  [${o.method}] ${o.baseUrl}${o.path}',
            name: 'ApiService',
          );
          h.next(o);
        },
        onResponse: (res, h) {
          final request = res.requestOptions;
          dev.log(
            '✅  [${request.method}] ${request.baseUrl}${request.path} (${res.statusCode})',
            name: 'ApiService',
          );
          h.next(res);
        },
        onError: (err, h) {
          final request = err.requestOptions;
          dev.log(
            '❌  [${request.method}] ${request.baseUrl}${request.path} (${err.response?.statusCode ?? 'NO_RESPONSE'})',
            name: 'ApiService',
            error: err.message,
          );
          h.next(err);
        },
      ),
    );
    _dio.interceptors.add(
      LogInterceptor(
        request: true,
        requestBody: true,
        responseHeader: false,
        responseBody: true,
      ),
    );
  }

  final Dio _dio;

  Future<LoginResult> login({
    required String email,
    required String password,
  }) async {
    try {
      final res = await _dio.post(
        '/api/auth/login',
        data: {'email': email, 'password': password},
      );
      final data = res.data as Map<String, dynamic>;
      final access = data['access_token'] as String?;
      if (access == null || access.isEmpty) {
        throw Exception('No access_token in response');
      }
      return LoginResult(
        access: access,
        refresh: data['refresh_token'] as String?,
        expires: (data['expires_in'] as num?)?.toInt(),
      );
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final body = e.response?.data;
      final msg = 'Login failed ($code): ${_pretty(body) ?? e.message}';
      throw Exception(msg);
    }
  }

  Future<void> logout() async {
    try {
      await _dio.post('/api/auth/logout');
    } catch (_) {
      /* 서버 미구현이면 무시 */
    }
  }

  String? _pretty(dynamic data) {
    if (data == null) return null;
    try {
      return data.toString();
    } catch (_) {
      return null;
    }
  }
}

class LoginResult {
  final String access;
  final String? refresh;
  final int? expires;
  const LoginResult({required this.access, this.refresh, this.expires});
}

extension AuthApi on ApiService {
  Future<void> signup({
    required String email,
    required String password,
    required String name,
    required String phone,
  }) async {
    try {
      await _dio.post(
        '/api/auth/signup',
        data: {
          'email': email,
          'password': password,
          'name': name,
          'phone': phone,
        },
      );
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final msg =
          (e.response?.data is Map && e.response?.data['detail'] != null)
          ? e.response?.data['detail'].toString()
          : e.message ?? 'Sign up failed';
      throw Exception('Sign up failed ($code): $msg');
    }
  }
}

extension ProfileApi on ApiService {
  Future<UserProfile> getMe() async {
    try {
      final res = await _dio.get('/api/profile/');
      final data = res.data;
      if (data is! Map<String, dynamic>) {
        throw const FormatException('Invalid profile payload');
      }
      return UserProfile.fromJson(data);
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final msg =
          _pretty(e.response?.data) ?? e.message ?? 'Failed to load profile';
      throw Exception('Profile fetch failed ($code): $msg');
    }
  }

  Future<UserProfile> updateProfile({required String name}) async {
    try {
      final res = await _dio.put('/api/profile/', data: {'name': name});
      final data = res.data;
      if (data is! Map<String, dynamic>) {
        throw const FormatException('Invalid profile payload');
      }
      return UserProfile.fromJson(data);
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final msg =
          _pretty(e.response?.data) ?? e.message ?? 'Failed to update profile';
      throw Exception('Profile update failed ($code): $msg');
    }
  }
}

extension DeviceManagementApi on ApiService {
  Future<List<DeviceDto>> getDevices() async {
    try {
      final res = await _dio.get('/api/devices');
      final list = res.data as List<dynamic>;
      return list
          .map((e) => DeviceDto.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      final msg = e.response?.data ?? e.message;
      throw Exception('Failed to load devices: $msg');
    }
  }

  Future<List<DiscoveredDevice>> discoverWifiDevices() async {
    try {
      final res = await _dio.post('/api/devices/discover/wifi');
      final list = res.data as List<dynamic>;
      return list
          .map((e) => DiscoveredDevice.fromJson(e as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      final msg = e.response?.data ?? e.message;
      throw Exception('Failed to scan devices: $msg');
    }
  }

  Future<DeviceDto> pairDevice(PairDeviceRequest body) async {
    try {
      final res = await _dio.post('/api/devices/pair', data: body.toJson());
      return DeviceDto.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final msg = e.response?.data ?? e.message;
      throw Exception('Pairing failed: $msg');
    }
  }

  Future<void> deleteDevice(String deviceId) async {
    try {
      await _dio.delete('/api/devices/$deviceId');
    } on DioException catch (e) {
      final msg = e.response?.data ?? e.message;
      throw Exception('Failed to delete device: $msg');
    }
  }

  Future<DeviceStatus> getDeviceStatus(String deviceId) async {
    try {
      final res = await _dio.get('/api/devices/status/$deviceId');
      return DeviceStatus.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final msg = e.response?.data ?? e.message;
      throw Exception('디바이스 상태를 가져오지 못했습니다: $msg');
    }
  }
}

extension HomeApi on ApiService {
  Future<bool> getAncEnabled() async {
    try {
      final res = await _dio.get('/api/home/anc');
      final data = res.data;
      if (data is Map<String, dynamic> && data['anc_enabled'] is bool) {
        return data['anc_enabled'] as bool;
      }
      throw const FormatException('Invalid ANC payload');
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final msg = _pretty(e.response?.data) ?? e.message;
      throw Exception('ANC 상태를 불러오지 못했습니다 ($code): $msg');
    }
  }

  Future<bool> toggleAnc({required bool enabled}) async {
    try {
      final res = await _dio.post(
        '/api/home/anc/toggle',
        data: {'enabled': enabled},
      );
      final data = res.data;
      if (data is Map<String, dynamic> && data['anc_enabled'] is bool) {
        return data['anc_enabled'] as bool;
      }
      // 일부 백엔드 구현에서 anc_enabled를 반환하지 않을 경우 요청한 enabled로 간주
      return enabled;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final msg = _pretty(e.response?.data) ?? e.message;
      throw Exception('ANC 상태 변경에 실패했습니다 ($code): $msg');
    }
  }
}
