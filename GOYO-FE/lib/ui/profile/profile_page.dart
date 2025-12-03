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

  Future<void> _showNoiseLogs(BuildContext context) async {
    final cs = Theme.of(context).colorScheme;
    final logs = [
      const ('08:05', '주방 환풍기가 자동으로 억제되었습니다 (45%)'),
      const ('12:22', '통화 하는 동안 거실 TV 음량이 제한되었습니다'),
      const ('19:40', '스마트 의자가 집중모드 ANC 프로필로 조정되었습니다'),
    ];

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.insights_outlined, color: cs.primary),
                  const SizedBox(width: 8),
                  const Text(
                    '노이즈 로그',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              const Text('소음 패턴과 기기 사용 이력의 데이터 로그'),
              const SizedBox(height: 12),
              ...logs.map(
                (log) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(
                    backgroundColor: cs.primary.withOpacity(.12),
                    child: Icon(Icons.schedule, color: cs.primary),
                  ),
                  title: Text(log.$2),
                  subtitle: Text(log.$1),
                ),
              ),
            ],
          ),
        );
      },
    );
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
              '노이즈 모드',
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
                  label: Text('일반 모드'),
                  icon: Icon(Icons.hearing_disabled),
                ),
                ButtonSegment(
                  value: AncMode.focus,
                  label: Text('집중 모드'),
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
                      title: const Text('자동 모드'),
                      subtitle: const Text('주변 소음에 맞춰 소음 억제를 자동 조정'),
                    ),
                    const SizedBox(height: 8),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: CircleAvatar(
                        backgroundColor: cs.primary.withOpacity(.12),
                        child: Icon(Icons.map_outlined, color: cs.primary),
                      ),
                      title: const Text('Noise map'),
                      subtitle: const Text('소음 패턴 및 기기 사용 이력 데이터 로그'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _showNoiseLogs(context),
                    ),
                    const SizedBox(height: 4),
                    const Text('최근 소음 패턴과 기기 반응을 확인하려면 탭하세요.'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

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

  void _syncController(String name) {
    _lastLoadedName = name;
    nameCtrl.value = TextEditingValue(
      text: name,
      selection: TextSelection.collapsed(offset: name.length),
    );
  }
}
