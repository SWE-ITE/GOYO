import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:goyo_app/features/anc/anc_store.dart';
import 'package:goyo_app/features/auth/auth_provider.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final nameCtrl = TextEditingController();
  String? _lastLoadedName;

  @override
  void initState() {
    super.initState();
    final store = context.read<AncStore>();
    nameCtrl.text = store.userName;
    _lastLoadedName = store.userName;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final profileName = context.read<AuthProvider>().me?.name;
      if (profileName != null && profileName.isNotEmpty) {
        _syncController(profileName);
      }
    });
  }

  @override
  void dispose() {
    nameCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final auth = context.watch<AuthProvider>();
    final profile = auth.me;

    if (auth.profileLoading && profile == null) {
      return const Scaffold(
        body: SafeArea(child: Center(child: CircularProgressIndicator())),
      );
    }

    if (auth.profileError != null && profile == null) {
      return Scaffold(
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const Icon(
                  Icons.error_outline,
                  size: 48,
                  color: Colors.redAccent,
                ),
                const SizedBox(height: 16),
                Text(
                  '프로필 정보를 불러오지 못했습니다.',
                  style: Theme.of(context).textTheme.titleMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  auth.profileError!,
                  textAlign: TextAlign.center,
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(color: cs.error),
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: auth.profileLoading
                      ? null
                      : () => context.read<AuthProvider>().loadMe(),
                  child: const Text('다시 시도'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (profile?.name != null && profile!.name != _lastLoadedName) {
      _syncController(profile.name);
    }

    final anc = context.watch<AncStore>();
    final current = anc.mode;

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (auth.profileError != null)
              Card(
                color: cs.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: cs.onErrorContainer),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          auth.profileError!,
                          style: TextStyle(color: cs.onErrorContainer),
                        ),
                      ),
                      TextButton(
                        onPressed: auth.profileLoading
                            ? null
                            : () => context.read<AuthProvider>().loadMe(),
                        child: const Text('새로고침'),
                      ),
                    ],
                  ),
                ),
              ),
            if (auth.profileError != null) const SizedBox(height: 12),
            // ── User info ─────────────────────────────────────────────
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 28,
                      backgroundColor: cs.primary.withOpacity(.15),
                      child: Icon(Icons.person, color: cs.primary, size: 28),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: TextField(
                        controller: nameCtrl,
                        decoration: const InputDecoration(
                          labelText: 'Your name',
                          hintText: 'Enter your display name',
                          prefixIcon: Icon(Icons.badge_outlined),
                        ),
                        enabled: !auth.profileUpdating,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // ── Sound mode (Normal / Focus) ──────────────────────────
            Text(
              'Preferred sound mode',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: cs.onSurface,
              ),
            ),
            const SizedBox(height: 8),
            SegmentedButton<AncMode>(
              segments: const [
                ButtonSegment(
                  value: AncMode.normal,
                  label: Text('Normal'),
                  icon: Icon(Icons.hearing_disabled),
                ),
                ButtonSegment(
                  value: AncMode.focus,
                  label: Text('Focus'),
                  icon: Icon(Icons.center_focus_strong),
                ),
              ],
              selected: {current},
              onSelectionChanged: (s) {
                final selected = s.first;
                anc.setMode(selected);

                // UX 피드백: 무엇이 바뀌었는지 명확히
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      selected == AncMode.focus
                          ? 'Focus Mode: 모든 소음 규칙 ON + 강도 최대로 전환됐어요.'
                          : 'Normal Mode: 사용자 개별 토글 상태를 적용했어요.',
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 16),

            // ── ANC preset for current mode ──────────────────────────
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.hearing, color: cs.primary),
                        const SizedBox(width: 8),
                        Text(
                          'ANC preset for "${anc.mode.name.toUpperCase()}"',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: cs.onSurface,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      value: anc.auto,
                      onChanged: (v) => context.read<AncStore>().setAuto(v),
                      title: const Text('Automatic mode'),
                      subtitle: const Text(
                        'Adjust suppression based on ambient noise',
                      ),
                    ),
                    const SizedBox(height: 8),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Suppression intensity'),
                      subtitle: Slider(
                        value: anc.intensity,
                        onChanged: (v) =>
                            context.read<AncStore>().setIntensity(v),
                        min: 0.0,
                        max: 1.0,
                      ),
                      trailing: Text('${(anc.intensity * 100).round()}%'),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      anc.mode == AncMode.focus
                          ? '※ 집중모드에서는 홈의 모든 노이즈 규칙이 자동으로 ON이며 강도도 최대입니다.'
                          : '※ 일반모드에서는 사용자가 켠 규칙만 적용됩니다.',
                      style: TextStyle(color: cs.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // ── Save changes ─────────────────────────────────────────
            FilledButton(
              onPressed: auth.profileUpdating ? null : _save,
              child: auth.profileUpdating
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save changes'),
            ),
            const SizedBox(height: 10),

            // 로그아웃 버튼(그대로 유지)
            FilledButton.tonalIcon(
              onPressed: () => Navigator.of(
                context,
              ).pushNamedAndRemoveUntil('/login', (route) => false),
              label: const Text('Log out'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _save() async {
    final auth = context.read<AuthProvider>();
    final trimmed = nameCtrl.text.trim();
    if (trimmed.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('이름을 입력해 주세요.')));
      return;
    }

    // 1) 이름 저장 (백엔드 연동 지점)
    try {
      await auth.updateMyName(trimmed);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile updated successfully')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('이름 변경에 실패했어요: $e')));
    }
  }

  // 2) 모드/프리셋 저장 필요 시 여기서 API 호출 추가
  // await api.saveAncPreset(mode: store.mode, auto: store.auto, intensity: store.intensity);

  void _syncController(String name) {
    _lastLoadedName = name;
    nameCtrl.value = TextEditingValue(
      text: name,
      selection: TextSelection.collapsed(offset: name.length),
    );
  }
}
