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
  bool ancOn = true;

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
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        ancOn ? 'ANC ENABLED' : 'ANC DISABLED',
                        style: TextStyle(
                          color: ancOn ? cs.primary : cs.onSurfaceVariant,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        ancOn
                            ? 'Noise cancelling is active across your devices.'
                            : 'Toggle on to activate ambient noise control.',
                        style: TextStyle(color: cs.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
                Switch(
                  value: ancOn,
                  onChanged: (v) => setState(() => ancOn = v),
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
            onRename: (name) => setState(() => r.title = name),
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
  final ValueChanged<String> onRename;

  const _NoiseRuleTile({
    required this.rule,
    required this.onToggle,
    required this.onDelete,
    required this.onRename,
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
                  onPressed: locked
                      ? null
                      : () => _promptRename(context, rule.title),
                  icon: const Icon(Icons.edit_outlined),
                  tooltip: 'Rename rule',
                ),
                IconButton(
                  onPressed: locked ? null : onDelete,
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

  Future<void> _promptRename(BuildContext context, String current) async {
    final controller = TextEditingController(text: current);
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Rename noise rule'),
          content: TextField(
            controller: controller,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Rule name',
              hintText: '예) 공기청정기 소리',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () {
                final trimmed = controller.text.trim();
                if (trimmed.isEmpty) return;
                Navigator.pop(context, trimmed);
              },
              child: const Text('저장'),
            ),
          ],
        );
      },
    );

    if (result != null && result.isNotEmpty) {
      onRename(result);
    }
  }
}

class NoiseRule {
  NoiseRule({required this.title, required this.icon, required this.enabled});

  String title;
  IconData icon;
  bool enabled;
}
