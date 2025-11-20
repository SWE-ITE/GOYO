import 'package:flutter/material.dart';
import 'package:goyo_app/features/anc/anc_store.dart';
import 'package:provider/provider.dart';

/// 홈 탭: ANC 토글 + 내가 규정한 소음 리스트
class HomeTab extends StatefulWidget {
  const HomeTab({super.key});

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  bool ancOn = false;

  final List<NoiseRule> rules = [
    NoiseRule(title: '냉장고 소리', icon: Icons.kitchen, enabled: true),
    NoiseRule(title: '에어컨 소리', icon: Icons.ac_unit, enabled: true),
    NoiseRule(title: '선풍기 소리', icon: Icons.wind_power, enabled: false),
  ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final anc = context.watch<AncStore>();
    final isFocus = anc.mode == AncMode.focus;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ANC 마스터 토글
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: cs.primary.withOpacity(.15),
                  child: Icon(Icons.hearing, color: cs.primary),
                ),
                const SizedBox(width: 12),
                const Text(
                  'FOCUS MODE',
                  style: TextStyle(
                    color: Colors.red,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ),
        if (isFocus)
          Padding(
            padding: const EdgeInsets.only(top: 6, bottom: 6),
            child: Text(
              'Focus Mode: all rules ON & 100% — editing disabled.',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
          ),
        const SizedBox(height: 8),

        ...rules.map(
          (r) => _NoiseRuleTile(
            rule: r,
            locked: isFocus,
            onToggle: (e) => setState(() => r.enabled = e),
            onDelete: () => setState(() => rules.remove(r)),
          ),
        ),
      ],
    );
  }
}

class _NoiseRuleTile extends StatelessWidget {
  final NoiseRule rule;
  final bool locked;
  final ValueChanged<bool> onToggle;
  final VoidCallback onDelete;

  const _NoiseRuleTile({
    required this.rule,
    required this.onToggle,
    required this.onDelete,
    this.locked = false,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final disabled = locked;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 상단 행: 아이콘 + 제목 + 액션들
            Row(
              children: [
                Icon(rule.icon, color: cs.primary),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    rule.title,
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: cs.onSurface,
                    ),
                  ),
                ),
                IconButton(
                  onPressed: onDelete,
                  icon: const Icon(Icons.delete_outline),
                  tooltip: 'Delete rule',
                ),
                Switch(
                  value: rule.enabled,
                  onChanged: disabled ? null : onToggle,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class NoiseRule {
  NoiseRule({required this.title, required this.icon, required this.enabled});

  String title;
  IconData icon;
  bool enabled;
}
