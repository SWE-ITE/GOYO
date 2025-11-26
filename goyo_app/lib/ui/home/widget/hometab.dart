import 'package:flutter/material.dart';
import 'package:goyo_app/features/anc/anc_store.dart';
import 'package:provider/provider.dart';
import 'package:goyo_app/data/services/api_service.dart';

/// 홈 탭: ANC 토글 + 내가 규정한 소음 리스트
class HomeTab extends StatefulWidget {
  const HomeTab({super.key});

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  bool? ancOn;
  bool loadingAnc = false;
  bool togglingAnc = false;
  String? ancError;

  final List<NoiseRule> rules = [
    NoiseRule(title: '냉장고 소리', icon: Icons.kitchen, enabled: true),
    NoiseRule(title: '에어컨 소리', icon: Icons.ac_unit, enabled: true),
    NoiseRule(title: '선풍기 소리', icon: Icons.wind_power, enabled: false),
  ];

  @override
  void initState() {
    super.initState();
    _loadAnc();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final anc = context.watch<AncStore>();
    final isFocus = anc.mode == AncMode.focus;
    final isAncOn = ancOn ?? false;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ANC 마스터 토글 (중앙 원형 아이콘 버튼 + 텍스트)
        Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Material(
                color: isAncOn
                    ? cs.primary.withOpacity(0.25)
                    : cs.surfaceVariant,
                shape: const CircleBorder(),
                child: InkWell(
                  customBorder: const CircleBorder(),
                  onTap: (loadingAnc || togglingAnc)
                      ? null
                      : () => _toggleAnc(!isAncOn),
                  child: SizedBox(
                    width: 96,
                    height: 96,
                    child: Center(
                      child: Icon(
                        Icons.hearing,
                        size: 56,
                        color: isAncOn
                            ? cs.onPrimaryContainer
                            : cs.onSurfaceVariant,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'anc',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: isAncOn ? cs.primary : cs.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        if (loadingAnc || togglingAnc)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: LinearProgressIndicator(minHeight: 3),
          ),
        if (ancError != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(
              ancError!,
              style: TextStyle(color: cs.error, fontSize: 12),
            ),
          ),

        const SizedBox(height: 30),
        Padding(
          padding: const EdgeInsets.only(left: 10, bottom: 8),
          child: Text(
            '소음 리스트',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: cs.onSurface,
            ),
          ),
        ),
        if (isFocus)
          Padding(
            padding: const EdgeInsets.only(top: 6, bottom: 6, left: 8),
            child: Text(
              '집중 모드: 모든 노이즈 감소 규칙이 활성화 되었습니다.',
              style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant),
            ),
          ),
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

  Future<void> _loadAnc() async {
    setState(() {
      loadingAnc = true;
      ancError = null;
    });

    try {
      final enabled = await context.read<ApiService>().getAncEnabled();
      if (!mounted) return;
      setState(() => ancOn = enabled);
    } catch (e) {
      if (!mounted) return;
      setState(() => ancError = 'ANC 상태를 불러오지 못했습니다: $e');
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('ANC 상태를 불러오지 못했습니다: $e')));
    } finally {
      if (mounted) setState(() => loadingAnc = false);
    }
  }

  Future<void> _toggleAnc(bool enabled) async {
    if (togglingAnc || loadingAnc) return;
    final previous = ancOn ?? false;

    setState(() {
      ancOn = enabled;
      togglingAnc = true;
      ancError = null;
    });

    try {
      final result = await context.read<ApiService>().toggleAnc(
        enabled: enabled,
      );
      if (!mounted) return;
      setState(() => ancOn = result);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        ancOn = previous;
        ancError = 'ANC 상태 변경 실패: $e';
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('ANC 상태 변경 실패: $e')));
    } finally {
      if (mounted) setState(() => togglingAnc = false);
    }
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
