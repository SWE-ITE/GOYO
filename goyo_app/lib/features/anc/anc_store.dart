import 'package:flutter/material.dart';

enum AncMode { normal, focus }

class NoiseRuleModel {
  final String id;
  final String title;
  final IconData icon;
  int intensity; // 0~100
  bool enabled;

  NoiseRuleModel({
    required this.id,
    required this.title,
    required this.icon,
    required this.intensity,
    required this.enabled,
  });

  NoiseRuleModel copyWith({int? intensity, bool? enabled}) => NoiseRuleModel(
    id: id,
    title: title,
    icon: icon,
    intensity: intensity ?? this.intensity,
    enabled: enabled ?? this.enabled,
  );
}

class AncStore extends ChangeNotifier {
  
  String userName;
  AncStore({String? initialUserName})
    : userName = (initialUserName?.trim().isNotEmpty ?? false)
          ? initialUserName!.trim()
          : 'User' {
    // ... 기존 초기화(룰, _preferredEnabled 등)는 그대로
  }
  // AuthProvider에서 넘어온 이름으로 동기화
  void setUserName(String? name) {
    if (name == null) return;
    final n = name.trim();
    if (n.isEmpty || n == userName) return;
    userName = n;
    notifyListeners();
  }

  // 현재 모드 (normal | focus)
  AncMode mode = AncMode.focus;

  // 자동/강도 프리셋 (0~1)
  bool auto = false;
  double intensity = 0.8;

  // 홈의 소음 룰들(앱 시작 더미)
  List<NoiseRuleModel> rules = [
    NoiseRuleModel(
      id: 'hum',
      title: 'Low-frequency hum',
      icon: Icons.vibration,
      intensity: 45,
      enabled: true,
    ),
    NoiseRuleModel(
      id: 'fan',
      title: 'Fan noise',
      icon: Icons.toys,
      intensity: 50,
      enabled: false,
    ),
    NoiseRuleModel(
      id: 'impact',
      title: 'Impact noise',
      icon: Icons.sensors,
      intensity: 60,
      enabled: true,
    ),
  ];

  // 일반모드에서의 "사용자 개별 선택" 상태를 보존
  final Map<String, bool> _preferredEnabled = {};

  // 이름 업데이트(백엔드 연동 시 API 호출 후 성공 시 반영)
  Future<void> updateUserName(String newName) async {
    final n = newName.trim();
    if (n.isEmpty) return;
    userName = n;
    // TODO: await api.updateProfile(userName: n);
    notifyListeners();
  }

  // 프로필의 자동/강도 프리셋 변경
  void setAuto(bool v) {
    auto = v;
    notifyListeners();
  }

  void setIntensity(double v) {
    intensity = v.clamp(0.0, 1.0);
    notifyListeners();
  }

  // 모드 전환: 요구사항 핵심
  void setMode(AncMode m) {
    mode = m;

    if (mode == AncMode.focus) {
      // 집중모드: 모든 룰 ON + 강도 100%
      rules = rules
          .map((r) => r.copyWith(intensity: 100, enabled: true))
          .toList();
    } else {
      // 일반모드: 사용자 개별 토글 복원
      rules = rules.map((r) {
        final keep = _preferredEnabled[r.id] ?? r.enabled;
        return r.copyWith(enabled: keep);
      }).toList();
    }
    notifyListeners();
  }

  // 홈 탭에서 유저가 개별 룰 토글할 때, 일반모드의 선호 상태로 기록
  void setPreferredEnabled(String ruleId, bool enabled) {
    _preferredEnabled[ruleId] = enabled;
    // 현재 모드가 normal이면 실제 룰에도 바로 반영
    if (mode == AncMode.normal) {
      rules = rules
          .map((r) => r.id == ruleId ? r.copyWith(enabled: enabled) : r)
          .toList();
      notifyListeners();
    }
  }

  // 홈 탭에서 슬라이더 강도 조절 시
  void setRuleIntensity(String ruleId, int percent) {
    final p = percent.clamp(0, 100);
    rules = rules
        .map((r) => r.id == ruleId ? r.copyWith(intensity: p) : r)
        .toList();
    notifyListeners();
  }
}
