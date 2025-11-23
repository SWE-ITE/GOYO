import 'package:flutter/material.dart';
import 'package:goyo_app/core/auth/token_manager.dart';
import 'package:goyo_app/features/auth/auth_provider.dart';
import 'package:goyo_app/data/services/api_service.dart';
import 'package:provider/provider.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final emailCtrl = TextEditingController();
  final pwCtrl = TextEditingController();
  bool loading = false;

  @override
  void dispose() {
    emailCtrl.dispose();
    pwCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    print('[LOGIN] _submit start');
    if (loading) return;

    final isValid = _formKey.currentState?.validate() ?? false;
    print('[LOGIN] form valid? $isValid');
    if (!isValid) return;

    setState(() => loading = true);
    try {
      final email = emailCtrl.text.trim();
      final pw = pwCtrl.text;

      print('[LOGIN] calling API…');
      final result = await context.read<ApiService>().login(
        email: email,
        password: pw,
      );

      await TokenManager.saveToken(result.access);
      await context.read<AuthProvider>().setToken(result.access);

      if (!mounted) return;
      print('[LOGIN] navigate /home');
      Navigator.of(context).pushReplacementNamed('/home');
    } catch (e) {
      if (!mounted) return;
      print('[LOGIN][ERR] $e');
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: Form(
              key: _formKey,
              autovalidateMode: AutovalidateMode.onUserInteraction,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // 로고
                    CircleAvatar(
                      radius: 36,
                      backgroundColor: cs.primary.withOpacity(0.15),
                      child: Icon(Icons.hearing, color: cs.primary, size: 36),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Welcome to ANC',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        color: cs.onSurface,
                      ),
                    ),
                    const SizedBox(height: 24),

                    // ID
                    Text('ID', style: TextStyle(color: cs.onSurfaceVariant)),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: emailCtrl,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(labelText: 'Email'),
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

                    // PW
                    Text(
                      'Password',
                      style: TextStyle(color: cs.onSurfaceVariant),
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: pwCtrl,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Password'),
                      validator: (v) =>
                          (v == null || v.isEmpty) ? '비밀번호를 입력해 주세요' : null,
                      onFieldSubmitted: (_) => _submit(),
                    ),
                    const SizedBox(height: 16),

                    // 로그인 버튼
                    ElevatedButton(
                      onPressed: loading
                          ? null
                          : () {
                              print('[LOGIN] button tapped');
                              _submit();
                            },
                      child: loading
                          ? const SizedBox(
                              height: 22,
                              width: 22,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Sign in'),
                    ),
                    const SizedBox(height: 12),
                    TextButton(
                      onPressed: loading
                          ? null
                          : () => Navigator.of(context).pushNamed('/signup'),
                      child: const Text('아직 계정이 없어요? 회원가입'),
                    ),
                    const SizedBox(height: 7),
                    TextButton(
                      onPressed: loading
                          ? null
                          : () => Navigator.of(context).pushNamed('/recover'),
                      child: const Text('ID/PW 찾기'),
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
