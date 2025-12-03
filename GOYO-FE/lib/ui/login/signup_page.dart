import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:goyo_app/data/services/api_service.dart';

class SignUpPage extends StatefulWidget {
  const SignUpPage({super.key});

  @override
  State<SignUpPage> createState() => _SignUpPageState();
}

class _SignUpPageState extends State<SignUpPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _pwCtrl = TextEditingController();
  final _pwConfirmCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();

  bool _obscure = true;
  bool _obscureConfirm = true;
  bool _loading = false;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _pwCtrl.dispose();
    _pwConfirmCtrl.dispose();
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_loading) return;
    final ok = _formKey.currentState?.validate() ?? false;
    if (!ok) return;

    setState(() => _loading = true);
    try {
      final email = _emailCtrl.text.trim();
      final pw = _pwCtrl.text;
      final name = _nameCtrl.text.trim();
      final phone = _phoneCtrl.text.trim();

      await context.read<ApiService>().signup(
        email: email,
        password: pw,
        name: name,
        phone: phone,
      );

      if (!mounted) return;
      // 회원가입 성공 → 안내 후 로그인으로
      await showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('가입 완료'),
          content: const Text('이메일 인증을 완료하시면 로그인할 수 있어요.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('확인'),
            ),
          ],
        ),
      );
      if (!mounted) return;
      Navigator.of(context).pop(); // 뒤로 (로그인 페이지로 복귀)
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('회원가입')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: Form(
              key: _formKey,
              autovalidateMode: AutovalidateMode.onUserInteraction,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // 이름
                    Text('이름', style: TextStyle(color: cs.onSurfaceVariant)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _nameCtrl,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(hintText: '홍길동'),
                      validator: (v) => (v == null || v.trim().isEmpty)
                          ? '이름을 입력해 주세요'
                          : null,
                    ),
                    const SizedBox(height: 14),

                    // 이메일
                    Text('이메일', style: TextStyle(color: cs.onSurfaceVariant)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _emailCtrl,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        hintText: 'name@example.com',
                      ),
                      validator: (v) {
                        final s = (v ?? '').trim();
                        if (s.isEmpty) return '이메일을 입력해 주세요';
                        final ok = RegExp(
                          r'^[^@\s]+@[^@\s]+\.[^@\s]+$',
                        ).hasMatch(s);
                        return ok ? null : '올바른 이메일 형식이 아닙니다';
                      },
                    ),
                    const SizedBox(height: 14),

                    // 비밀번호
                    Text(
                      '비밀번호 (8자 이상)',
                      style: TextStyle(color: cs.onSurfaceVariant),
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _pwCtrl,
                      obscureText: _obscure,
                      textInputAction: TextInputAction.next,
                      decoration: InputDecoration(
                        hintText: '영문/숫자/특수문자 조합 권장',
                        suffixIcon: IconButton(
                          onPressed: () => setState(() => _obscure = !_obscure),
                          icon: Icon(
                            _obscure ? Icons.visibility_off : Icons.visibility,
                          ),
                        ),
                      ),
                      validator: (v) {
                        final s = v ?? '';
                        if (s.isEmpty) return '비밀번호를 입력해 주세요';
                        if (s.length < 8) return '8자 이상 입력해 주세요';
                        return null;
                      },
                    ),
                    const SizedBox(height: 14),

                    // 비밀번호 확인
                    Text(
                      '비밀번호 확인',
                      style: TextStyle(color: cs.onSurfaceVariant),
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _pwConfirmCtrl,
                      obscureText: _obscureConfirm,
                      textInputAction: TextInputAction.next,
                      decoration: InputDecoration(
                        hintText: '비밀번호를 다시 입력해 주세요',
                        suffixIcon: IconButton(
                          onPressed: () => setState(
                            () => _obscureConfirm = !_obscureConfirm,
                          ),
                          icon: Icon(
                            _obscureConfirm
                                ? Icons.visibility_off
                                : Icons.visibility,
                          ),
                        ),
                      ),
                      validator: (v) {
                        final s = v ?? '';
                        if (s.isEmpty) return '비밀번호 확인을 입력해 주세요';
                        if (s != _pwCtrl.text) return '비밀번호가 일치하지 않습니다';
                        return null;
                      },
                    ),
                    const SizedBox(height: 14),
                    Text('전화번호', style: TextStyle(color: cs.onSurfaceVariant)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _phoneCtrl,
                      keyboardType: TextInputType.phone,
                      textInputAction: TextInputAction.done,
                      decoration: const InputDecoration(
                        hintText: '010-1234-5678',
                      ),
                      validator: (v) {
                        final s = (v ?? '').trim();
                        if (s.isEmpty) return '전화번호를 입력해 주세요';
                        // 아주 간단한 검증(숫자/하이픈만)
                        final ok = RegExp(r'^[0-9\-+ ]{9,}$').hasMatch(s);
                        return ok ? null : '전화번호 형식을 확인해 주세요';
                      },
                      onFieldSubmitted: (_) => _submit(),
                    ),
                    const SizedBox(height: 20),

                    FilledButton(
                      onPressed: _loading ? null : _submit,
                      child: _loading
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('회원가입'),
                    ),
                    const SizedBox(height: 12),

                    TextButton(
                      onPressed: _loading
                          ? null
                          : () => Navigator.of(context).pop(),
                      child: const Text('이미 계정이 있으신가요? 로그인'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
