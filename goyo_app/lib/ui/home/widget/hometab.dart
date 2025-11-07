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
      controllNoise: 45,
      enabled: true,
    ),
    NoiseRule(
      title: 'Fan noise',
      icon: Icons.toys,
      controllNoise: 50,
      enabled: false,
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
    final controller = TextEditingController(text: r.controllNoise.toString());
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
                labelText: 'controllNoise',
                hintText: 'e.g., 50',
                prefixIcon: Icon(Icons.graphic_eq),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () {
                // 바텀시트 Save 버튼
                final v = int.tryParse(controller.text.trim());
                if (v != null) {
                  setState(() => r.controllNoise = v.clamp(0, 100));
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

class _NoiseRuleTile extends StatefulWidget {
  final NoiseRule rule;
  final ValueChanged<bool> onToggle;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  // (선택) 외부에도 값 변경 통지하고 싶으면 콜백 추가 가능
  final ValueChanged<int>? onIntensityChanged;

  const _NoiseRuleTile({
    required this.rule,
    required this.onToggle,
    required this.onEdit,
    required this.onDelete,
    this.onIntensityChanged,
  });

  @override
  State<_NoiseRuleTile> createState() => _NoiseRuleTileState();
}

class _NoiseRuleTileState extends State<_NoiseRuleTile> {
  late int _intensity; // 0~100

  @override
  void initState() {
    super.initState();
    _intensity = (widget.rule.controllNoise).clamp(0, 100);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 상단 행: 아이콘 + 제목 + 액션들
            Row(
              children: [
                Icon(widget.rule.icon, color: cs.primary),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    widget.rule.title,
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: cs.onSurface,
                    ),
                  ),
                ),
                IconButton(
                  onPressed: widget.onEdit,
                  icon: const Icon(Icons.edit_outlined),
                  tooltip: 'Edit rule',
                ),
                IconButton(
                  onPressed: widget.onDelete,
                  icon: const Icon(Icons.delete_outline),
                  tooltip: 'Delete rule',
                ),
                Switch(value: widget.rule.enabled, onChanged: widget.onToggle),
              ],
            ),

            const SizedBox(height: 8),

            // 슬라이더 라벨
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Reduction intensity',
                  style: TextStyle(color: cs.onSurfaceVariant),
                ),
                Text(
                  '$_intensity %',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: cs.onSurface,
                  ),
                ),
              ],
            ),

            // 슬라이더 본체
            Slider.adaptive(
              value: _intensity.toDouble(),
              min: 0,
              max: 100,
              divisions: 20,
              onChanged: (v) => setState(() => _intensity = v.round()),
              onChangeEnd: (v) {
                final val = v.round().clamp(0, 100);
                widget.rule.controllNoise = val;
                widget.onIntensityChanged?.call(val);
              },
            ),
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
    int? controllNoise, // <- nullable로 받고
    required this.enabled,
  }) : controllNoise = (controllNoise ?? 50).clamp(0, 100); // <- 기본/범위 보정

  String title;
  IconData icon;
  int controllNoise;
  bool enabled;
}
