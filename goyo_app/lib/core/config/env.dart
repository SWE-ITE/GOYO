import 'package:flutter_dotenv/flutter_dotenv.dart';

class Env {
  static String get baseUrl =>
      dotenv.get('BASE_URL', fallback: 'http://3.36.205.186');
}
