import 'package:flutter/material.dart';

/// 홈 탭: ANC 토글 + 내가 규정한 소음 리스트
class HomeTab extends StatefulWidget {
  const HomeTab({super.key});

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  bool ancOn = false;

  final List<NoiseRule> rules = [
    NoiseRule(
      title: 'Low-frequency hum',
      icon: Icons.vibration,
      thresholdDb: 45,
      enabled: true,
    ),
    NoiseRule(
      title: 'Fan noise',
      icon: Icons.toys,
      thresholdDb: 50,
      enabled: false,
    ),
    NoiseRule(
      title: 'Impact noise',
      icon: Icons.sensors,
      thresholdDb: 60,
      enabled: true,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

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
                        'Active Noise Control',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: cs.onSurface,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        ancOn ? 'ANC is ON' : 'ANC is OFF',
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
        const SizedBox(height: 16),

        // 소음 규칙 리스트
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Noise List',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: cs.onSurface,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),

        ...rules.map(
          (r) => _NoiseRuleTile(
            rule: r,
            onToggle: (e) => setState(() => r.enabled = e),
            onEdit: () => _editRule(r),
            onDelete: () => setState(() => rules.remove(r)),
          ),
        ),
      ],
    );
  }

  void _editRule(NoiseRule r) async {
    final controller = TextEditingController(text: r.thresholdDb.toString());
    final cs = Theme.of(context).colorScheme;
    await showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (_) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Edit "${r.title}"',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: cs.onSurface,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Threshold (dB)',
                hintText: 'e.g., 50',
                prefixIcon: Icon(Icons.graphic_eq),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () {
                final v = int.tryParse(controller.text.trim());
                if (v != null) {
                  setState(() => r.thresholdDb = v);
                  Navigator.pop(context);
                }
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }
}

class _NoiseRuleTile extends StatelessWidget {
  final NoiseRule rule;
  final ValueChanged<bool> onToggle;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const _NoiseRuleTile({
    required this.rule,
    required this.onToggle,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Card(
      child: ListTile(
        leading: Icon(rule.icon, color: cs.primary),
        title: Text(rule.title),
        subtitle: Text('Threshold: ${rule.thresholdDb} dB'),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              onPressed: onEdit,
              icon: const Icon(Icons.edit_outlined),
            ),
            IconButton(
              onPressed: onDelete,
              icon: const Icon(Icons.delete_outline),
            ),
            Switch(value: rule.enabled, onChanged: onToggle),
          ],
        ),
      ),
    );
  }
}

class NoiseRule {
  NoiseRule({
    required this.title,
    required this.icon,
    required this.thresholdDb,
    required this.enabled,
  });

  String title;
  IconData icon;
  int thresholdDb;
  bool enabled;
}
