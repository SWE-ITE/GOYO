// lib/data/services/api_service.dart
import 'package:dio/dio.dart';
import 'package:goyo_app/core/config/env.dart';
import 'package:goyo_app/core/auth/token_manager.dart';

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
          if (t != null && t.isNotEmpty)
            o.headers['Authorization'] = 'Bearer $t';
          h.next(o);
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

// lib/data/services/api_service.dart
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
