import 'package:flutter/material.dart';

class AccountRecoveryPage extends StatefulWidget {
  const AccountRecoveryPage({super.key});

  @override
  State<AccountRecoveryPage> createState() => _AccountRecoveryPageState();
}

class _AccountRecoveryPageState extends State<AccountRecoveryPage>
    with SingleTickerProviderStateMixin {
  final _idFormKey = GlobalKey<FormState>();
  final _pwFormKey = GlobalKey<FormState>();

  final _idNameCtrl = TextEditingController();
  final _idPhoneCtrl = TextEditingController();
  final _idCodeCtrl = TextEditingController();

  final _pwNameCtrl = TextEditingController();
  final _pwEmailCtrl = TextEditingController();
  final _pwPhoneCtrl = TextEditingController();
  final _pwCodeCtrl = TextEditingController();

  @override
  void dispose() {
    _idNameCtrl.dispose();
    _idPhoneCtrl.dispose();
    _idCodeCtrl.dispose();
    _pwNameCtrl.dispose();
    _pwEmailCtrl.dispose();
    _pwPhoneCtrl.dispose();
    _pwCodeCtrl.dispose();
    super.dispose();
  }

  void _showPlaceholderMessage(String label) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('$label 기능은 준비 중입니다.')));
  }

  Widget _buildIdForm(ColorScheme cs) {
    return Form(
      key: _idFormKey,
      child: Column(
        children: [
          // 🔹 위쪽: 스크롤되는 입력 폼들
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const SizedBox(height: 20),
                Text(
                  "이름",
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _idNameCtrl,
                  decoration: const InputDecoration(labelText: '이름'),
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '이름을 입력해 주세요' : null,
                ),
                const SizedBox(height: 40),
                Text(
                  "전화번호",
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _idPhoneCtrl,
                  decoration: const InputDecoration(labelText: '전화번호'),
                  keyboardType: TextInputType.phone,
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '전화번호를 입력해 주세요' : null,
                ),
                const SizedBox(height: 40),
                Text(
                  "인증번호",
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _idCodeCtrl,
                  decoration: const InputDecoration(labelText: '인증번호'),
                  keyboardType: TextInputType.number,
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '인증번호를 입력해 주세요' : null,
                ),
                const SizedBox(height: 40),
              ],
            ),
          ),

          // 🔹 아래쪽: 화면 맨 아래에 고정되는 버튼
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                onPressed: () {
                  if (_idFormKey.currentState?.validate() ?? false) {
                    _showPlaceholderMessage('아이디 찾기');
                  }
                },
                child: const Text('아이디 찾기'),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPasswordForm(ColorScheme cs) {
    return Form(
      key: _pwFormKey,
      child: Column(
        children: [
          // 🔹 위쪽: 스크롤되는 입력 폼들
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const SizedBox(height: 12),

                // 이름
                Text(
                  "이름",
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _pwNameCtrl,
                  decoration: const InputDecoration(hintText: '이름을 입력해 주세요'),
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '이름을 입력해 주세요' : null,
                ),
                const SizedBox(height: 32),

                // 이메일
                Text(
                  "이메일",
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _pwEmailCtrl,
                  decoration: const InputDecoration(hintText: '이메일을 입력해 주세요'),
                  keyboardType: TextInputType.emailAddress,
                  validator: (v) {
                    final value = (v ?? '').trim();
                    if (value.isEmpty) return '이메일을 입력해 주세요';
                    final ok = value.contains('@') && value.contains('.');
                    return ok ? null : '올바른 이메일 형식이 아닙니다';
                  },
                ),
                const SizedBox(height: 32),

                // 전화번호
                Text(
                  "전화번호",
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _pwPhoneCtrl,
                  decoration: const InputDecoration(hintText: '전화번호를 입력해 주세요'),
                  keyboardType: TextInputType.phone,
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '전화번호를 입력해 주세요' : null,
                ),
                const SizedBox(height: 32),

                // 인증번호
                Text(
                  "인증번호",
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _pwCodeCtrl,
                  decoration: const InputDecoration(hintText: '인증번호를 입력해 주세요'),
                  keyboardType: TextInputType.number,
                  validator: (v) =>
                      (v == null || v.isEmpty) ? '인증번호를 입력해 주세요' : null,
                ),
                const SizedBox(height: 40),
              ],
            ),
          ),

          // 🔹 아래쪽: 화면 맨 아래에 고정되는 버튼
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                onPressed: () {
                  if (_pwFormKey.currentState?.validate() ?? false) {
                    _showPlaceholderMessage('비밀번호 찾기');
                  }
                },
                child: const Text('비밀번호 찾기'),
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('ID / PW 찾기'),
          bottom: const TabBar(
            tabs: [
              Tab(text: '아이디 찾기'),
              Tab(text: '비밀번호 찾기'),
            ],
          ),
        ),
        body: TabBarView(children: [_buildIdForm(cs), _buildPasswordForm(cs)]),
      ),
    );
  }
}
