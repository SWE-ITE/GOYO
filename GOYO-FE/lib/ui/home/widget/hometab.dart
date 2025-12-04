import 'package:flutter/material.dart';
import 'dart:math' as math;
import 'dart:async';
import 'package:goyo_app/features/anc/anc_store.dart';
import 'package:provider/provider.dart';
import 'package:goyo_app/data/services/api_service.dart';
import 'package:goyo_app/data/models/noise_appliance.dart';

/// 홈 탭: ANC 토글 + 내가 규정한 소음 리스트
class HomeTab extends StatefulWidget {
  const HomeTab({super.key});

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  bool? ancOn = false; // Default: OFF
  bool loadingAnc = false;
  bool togglingAnc = false;
  String? ancError;

  final List<NoiseRule> rules = [
    NoiseRule(title: '냉장고 소리', icon: Icons.kitchen, enabled: true),
    NoiseRule(title: '에어컨 소리', icon: Icons.ac_unit, enabled: true),
    NoiseRule(title: '선풍기 소리', icon: Icons.wind_power, enabled: false),
  ];

  // 실시간 폴링 (2초마다 DB 체크)
  Timer? _noisePollingTimer;
  static const int _pollingIntervalSeconds = 2;

  @override
  void initState() {
    super.initState();
    _loadAnc();
    _startNoisePoll(); // 폴링 시작
  }

  @override
  void dispose() {
    _stopNoisePoll(); // 폴링 정지
    super.dispose();
  }

  void _startNoisePoll() {
    _noisePollingTimer?.cancel();
    _noisePollingTimer = Timer.periodic(
      Duration(seconds: _pollingIntervalSeconds),
      (_) => _loadNoisyAppliances(),
    );
  }

  void _stopNoisePoll() {
    _noisePollingTimer?.cancel();
    _noisePollingTimer = null;
  }

  // DB에서 실시간 소음 감지 목록 조회
  Future<void> _loadNoisyAppliances() async {
    try {
      final appliances = await context.read<ApiService>().getNoisyAppliances();
      if (!mounted) return;

      debugPrint(
        '📱 API 응답 appliances: ${appliances.map((a) => '${a.name}(active=${a.isNoiseActive})').join(', ')}',
      );

      // API에서 받은 소음 가전 목록으로 로컬 rules 업데이트
      setState(() {
        // API에서 받은 is_noise_active=true인 가전들만 리스트에 유지
        List<NoiseRule> activeAppliances = [];

        for (final appliance in appliances) {
          // is_noise_active=false면 스킵 (리스트에서 제거)
          if (!appliance.isNoiseActive) {
            debugPrint('⏭️  스킵 (inactive): ${appliance.name}');
            continue;
          }

          debugPrint('🔍 매칭 시도: ${appliance.name}');

          // 정확한 이름 매칭 시도
          try {
            final existingRule = rules.firstWhere(
              (r) => r.title.toLowerCase() == appliance.name.toLowerCase(),
            );
            debugPrint(
              '✅ 정확한 매칭 성공: ${appliance.name} → ${existingRule.title}',
            );
            existingRule.enabled = true;
            activeAppliances.add(existingRule);
          } catch (e) {
            // 정확한 매칭 실패 → 부분 매칭 시도
            debugPrint('⚠️  정확한 매칭 실패, 부분 매칭 시도...');
            try {
              final existingRule = rules.firstWhere(
                (r) =>
                    appliance.name.toLowerCase().contains(
                      r.title.toLowerCase(),
                    ) ||
                    r.title.toLowerCase().contains(
                      appliance.name.toLowerCase(),
                    ),
              );
              debugPrint(
                '✅ 부분 매칭 성공: ${appliance.name} → ${existingRule.title}',
              );
              existingRule.enabled = true;
              activeAppliances.add(existingRule);
            } catch (e2) {
              // 그래도 매칭 실패 → 새 rule 추가
              debugPrint('❌ 매칭 실패, 새 rule 추가: ${appliance.name}');
              activeAppliances.add(
                NoiseRule(
                  title: appliance.name,
                  icon: _getIconForAppliance(appliance.name),
                  enabled: true,
                ),
              );
            }
          }
        }

        // rules를 API에서 받은 active 가전들로만 업데이트
        rules.clear();
        rules.addAll(activeAppliances);
      });
    } catch (e) {
      // 폴링 중 에러는 무시 (백그라운드에서 진행)
      debugPrint('❌ 소음 감지 조회 실패: $e');
    }
  }

  // 가전 이름으로 아이콘 결정
  IconData _getIconForAppliance(String name) {
    final nameLower = name.toLowerCase();
    if (nameLower.contains('냉장고') || nameLower.contains('fridge')) {
      return Icons.kitchen;
    } else if (nameLower.contains('에어컨') ||
        nameLower.contains('aircon') ||
        nameLower.contains('ac')) {
      return Icons.ac_unit;
    } else if (nameLower.contains('선풍기') || nameLower.contains('fan')) {
      return Icons.wind_power;
    }
    return Icons.speaker;
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
                    width: 120,
                    height: 120,
                    child: Center(
                      child: Icon(
                        Icons.hearing,
                        size: 80,
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
                isAncOn ? 'ANC ON' : 'ANC OFF',
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
        if (rules.isEmpty)
          SizedBox(
            height: 200,
            child: Center(
              child: Text(
                '감지된 소음이 없어요',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: cs.onSurfaceVariant,
                ),
              ),
            ),
          )
        else
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

class _NoiseRuleTile extends StatefulWidget {
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
  State<_NoiseRuleTile> createState() => _NoiseRuleTileState();
}

class _NoiseRuleTileState extends State<_NoiseRuleTile>
    with TickerProviderStateMixin {
  late AnimationController _waveController;
  late List<AnimationController> _pulseControllers;

  @override
  void initState() {
    super.initState();

    // 파동 애니메이션 (3개 바)
    _waveController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat();

    // 펄스 애니메이션 (3개)
    _pulseControllers = List.generate(
      3,
      (index) => AnimationController(
        duration: const Duration(milliseconds: 1200),
        vsync: this,
      )..repeat(),
    );

    // 각 펄스를 다른 시간에 시작
    for (int i = 0; i < _pulseControllers.length; i++) {
      _pulseControllers[i].forward(from: (i * 0.33) % 1.0);
    }
  }

  @override
  void dispose() {
    _waveController.dispose();
    for (var controller in _pulseControllers) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final disabled = widget.locked;
    final rule = widget.rule;

    return Card(
      elevation: rule.enabled ? 8 : 0,
      shadowColor: rule.enabled
          ? cs.primary.withOpacity(0.3)
          : Colors.transparent,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          gradient: rule.enabled
              ? LinearGradient(
                  colors: [
                    cs.primaryContainer.withOpacity(0.3),
                    cs.primaryContainer.withOpacity(0.1),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                )
              : null,
          border: rule.enabled
              ? Border.all(color: cs.primary.withOpacity(0.2), width: 1.5)
              : null,
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 상단 행: 아이콘 + 제목 + 액션들
              Row(
                children: [
                  // 동적 아이콘 (활성화시 애니메이션)
                  if (rule.enabled)
                    _AnimatedIcon(
                      icon: rule.icon,
                      color: cs.primary,
                      waveController: _waveController,
                    )
                  else
                    Icon(rule.icon, color: cs.primary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          rule.title,
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: cs.onSurface,
                            fontSize: 16,
                          ),
                        ),
                        if (rule.enabled)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              '소음이 감지되고 있어요',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: cs.primary,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                  if (!rule.enabled)
                    IconButton(
                      onPressed: disabled
                          ? null
                          : () => _promptRename(context, rule.title),
                      icon: const Icon(Icons.edit_outlined),
                      tooltip: 'Rename rule',
                    ),
                  if (!rule.enabled)
                    IconButton(
                      onPressed: disabled ? null : widget.onDelete,
                      icon: const Icon(Icons.delete_outline),
                      tooltip: 'Delete rule',
                    ),
                  Switch(
                    value: rule.enabled,
                    onChanged: disabled ? null : widget.onToggle,
                  ),
                ],
              ),
              // 활성화시 애니메이션 표시기
              if (rule.enabled) ...[
                const SizedBox(height: 12),
                _AnimatedSoundBar(
                  color: cs.primary,
                  pulseControllers: _pulseControllers,
                ),
              ],
            ],
          ),
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
      widget.onRename(result);
    }
  }
}

/// 동적 아이콘: 음파 수직 확대/축소 효과
class _AnimatedIcon extends StatelessWidget {
  final IconData icon;
  final Color color;
  final AnimationController waveController;

  const _AnimatedIcon({
    required this.icon,
    required this.color,
    required this.waveController,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: waveController,
      builder: (context, child) {
        final scale =
            1.0 + (math.sin(waveController.value * math.pi * 2) * 0.1);
        return Transform.scale(
          scale: scale,
          child: Icon(icon, color: color, size: 28),
        );
      },
    );
  }
}

/// 음성 활동을 표현하는 애니메이션 바
class _AnimatedSoundBar extends StatelessWidget {
  final Color color;
  final List<AnimationController> pulseControllers;

  const _AnimatedSoundBar({
    required this.color,
    required this.pulseControllers,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(
        3,
        (index) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: AnimatedBuilder(
            animation: pulseControllers[index],
            builder: (context, child) {
              final height =
                  24 +
                  (math.sin(pulseControllers[index].value * math.pi * 2) * 12);
              return Container(
                width: 4,
                height: height,
                decoration: BoxDecoration(
                  color: color.withOpacity(
                    0.4 +
                        (math.sin(pulseControllers[index].value * math.pi * 2) +
                                1) *
                            0.3,
                  ),
                  borderRadius: BorderRadius.circular(2),
                ),
              );
            },
          ),
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
