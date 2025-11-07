import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:goyo_app/features/anc/anc_store.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final nameCtrl = TextEditingController();
  bool saving = false;

  @override
  void initState() {
    super.initState();
    final store = context.read<AncStore>();
    nameCtrl.text = store.userName;
  }

  @override
  void dispose() {
    nameCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final anc = context.watch<AncStore>();
    final current = anc.mode;

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
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
              onPressed: saving ? null : _save,
              child: saving
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
    setState(() => saving = true);
    final store = context.read<AncStore>();

    // 1) 이름 저장 (백엔드 연동 지점)
    await store.updateUserName(nameCtrl.text);

    // 2) 모드/프리셋 저장 필요 시 여기서 API 호출 추가
    // await api.saveAncPreset(mode: store.mode, auto: store.auto, intensity: store.intensity);

    if (!mounted) return;
    setState(() => saving = false);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Profile updated successfully')),
    );
  }
}
