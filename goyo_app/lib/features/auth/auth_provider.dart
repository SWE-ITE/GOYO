// lib/features/auth/auth_provider.dart
import 'package:flutter/material.dart';
import 'package:goyo_app/core/auth/token_manager.dart';
import 'package:goyo_app/data/services/api_service.dart';

class AuthProvider with ChangeNotifier {
  AuthProvider(this._api);
  final ApiService _api;

  String? _token;
  String? get token => _token;
  bool get isLoggedIn => _token != null && _token!.isNotEmpty;

  /// 앱 시작 시 저장소에서 복원
  Future<void> bootstrap() async {
    _token = await TokenManager.getToken();
    notifyListeners();
  }

  Future<void> setToken(String token) async {
    _token = token; // 메모리 상태 업데이트
    await TokenManager.saveToken(token); // 보안 저장소 저장(선택: 여기서 함께)
    notifyListeners(); // 구독 중인 UI 리빌드
  }

  /// 로그인
  Future<void> login(
    String email,
    String password, {
    bool autoLogin = true,
  }) async {
    final result = await _api.login(email: email, password: password);
    _token = result.access;

    await TokenManager.saveToken(result.access);
    await TokenManager.setAutoLogin(autoLogin);

    // (필요시) refresh_token / expires 저장 키 추가해서 같이 보관 가능
    notifyListeners();
  }

  /// 로그아웃
  Future<void> logout() async {
    try {
      await _api.logout();
    } catch (_) {}
    _token = null;
    await TokenManager.clearAll();
    notifyListeners();
  }
}
