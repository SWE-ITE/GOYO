import 'package:flutter/material.dart';
import 'package:goyo_app/data/services/api_service.dart';
import 'package:goyo_app/features/anc/anc_store.dart';
import 'package:goyo_app/features/auth/auth_provider.dart';
import 'package:goyo_app/ui/home/home_page.dart';
import 'package:goyo_app/ui/login/login_page.dart';
import 'package:goyo_app/ui/login/signup_page.dart';
import 'package:goyo_app/ui/profile/profile_page.dart';
import 'package:provider/provider.dart';
import 'package:goyo_app/ui/login/recovery_page.dart';
import 'theme/app_theme.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // --dart-define=ENV=prod 로 넘기면 prod 파일 로드
  const envName = String.fromEnvironment('ENV', defaultValue: 'dev');
  await dotenv.load(fileName: 'assets/env/.env.$envName');

  runApp(const GoyoApp());
}

class GoyoApp extends StatelessWidget {
  const GoyoApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        // ApiService: 앱 전역에서 하나만
        Provider<ApiService>(create: (_) => ApiService()),
        // AuthProvider: ApiService를 주입받음
        ChangeNotifierProvider<AuthProvider>(
          create: (ctx) => AuthProvider(ctx.read<ApiService>())..bootstrap(),
        ),
        ChangeNotifierProxyProvider<AuthProvider, AncStore>(
          create: (_) => AncStore(initialUserName: 'User'),
          update: (_, auth, store) {
            // auth.me?.name 이 바뀌면 AncStore에 반영
            store ??= AncStore(initialUserName: 'User');
            store.setUserName(auth.me?.name);
            return store;
          },
        ),
      ],
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'GOYO',
        theme: AppTheme.light(), // ✅ 공통 테마
        darkTheme: AppTheme.dark(), // ✅ 다크 테마(선택)
        themeMode: ThemeMode.light, // 시스템/다크 스위칭 가능
        initialRoute: '/login',
        routes: {
          '/login': (_) => const LoginPage(),
          '/home': (_) => const HomePage(),
          '/profile': (_) => const ProfilePage(),
          '/signup': (_) => const SignUpPage(),
          '/recover': (_) => const AccountRecoveryPage(),
        },
      ),
    );
  }
}
