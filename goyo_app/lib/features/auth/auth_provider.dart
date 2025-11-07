// lib/features/auth/auth_provider.dart
import 'package:flutter/foundation.dart';
import 'package:goyo_app/data/services/api_service.dart';
import 'package:goyo_app/core/auth/token_manager.dart';

class UserProfile {
  final String email;
  final String name;
  final String? phone;
  final bool isVerified;
  final bool isActive;

  UserProfile({
    required this.email,
    required this.name,
    this.phone,
    required this.isVerified,
    required this.isActive,
  });

  factory UserProfile.fromJson(Map<String, dynamic> j) => UserProfile(
    email: j['email'] as String,
    name: (j['name'] ?? '') as String,
    phone: j['phone'] as String?,
    isVerified: (j['is_verified'] ?? false) as bool,
    isActive: (j['is_active'] ?? false) as bool,
  );
}

class AuthProvider extends ChangeNotifier {
  final ApiService api;
  AuthProvider(this.api);

  String? _accessToken;
  UserProfile? _me;
  bool _bootstrapped = false;

  String? get token => _accessToken;
  UserProfile? get me => _me;
  bool get isLoggedIn => _accessToken != null && _me != null;
  bool get bootstrapped => _bootstrapped;

  /// 앱 시작 시 호출(이미 main.dart에서 ..bootstrap()으로 호출 중)
  Future<void> bootstrap() async {
    try {
      _accessToken = await TokenManager.getToken();
      if (_accessToken != null && _accessToken!.isNotEmpty) {
        await loadMe();
      }
    } finally {
      _bootstrapped = true;
      notifyListeners();
    }
  }

  /// 로그인: 성공 시 토큰 저장 후 프로필 로드
  Future<void> login({required String email, required String password}) async {
    final res = await api.login(email: email, password: password);
    await setToken(res.access);
    await loadMe();
  }

  /// 토큰 설정(+보관)
  Future<void> setToken(String token) async {
    _accessToken = token;
    await TokenManager.saveToken(token);
    notifyListeners();
  }

  /// 로그아웃: 토큰/프로필 정리
  Future<void> logout() async {
    try {
      await api.logout(); // 서버 미구현이면 try/catch로 무시
    } catch (_) {}
    _accessToken = null;
    _me = null;
    await TokenManager.clearToken();
    notifyListeners();
  }

  /// 내 프로필 가져오기
  Future<void> loadMe() async {
    final data = await api.getMe(); // ApiService에 구현 필요(아래 참고)
    _me = data;
    notifyListeners();
  }

  /// 이름 변경 후 다시 로드(또는 로컬 반영)
  Future<void> updateMyName(String newName) async {
    final n = newName.trim();
    if (n.isEmpty) return;
    await api.updateProfile(name: n); // ApiService에 구현 필요
    await loadMe();
  }
}
