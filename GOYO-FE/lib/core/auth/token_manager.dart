// lib/core/auth/token_manager.dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenManager {
  static const _storage = FlutterSecureStorage();
  static const String _tokenKey = 'token';
  static const String _autoLoginKey = 'auto_login';
  static const String _boolTrue = '1';
  static const String _boolFalse = '0';

  static Future<void> setAutoLogin(bool enabled) async {
    await _storage.write(
      key: _autoLoginKey,
      value: enabled ? _boolTrue : _boolFalse,
    );
  }

  static Future<bool> isAutoLoginEnabled() async {
    final v = await _storage.read(key: _autoLoginKey);
    if (v == 'true' || v == 'false') {
      final normalized = (v == 'true') ? _boolTrue : _boolFalse;
      await _storage.write(key: _autoLoginKey, value: normalized);
      return normalized == _boolTrue;
    }
    return v == _boolTrue;
  }

  static Future<void> saveToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  static Future<String?> getToken() async {
    return await _storage.read(key: _tokenKey);
  }

  static Future<void> clearToken() async {
    await _storage.delete(key: _tokenKey);
  }

  static Future<void> clearAll() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _autoLoginKey);
  }
}
