class NoiseAppliance {
  final int id;
  final String name;
  final bool isNoiseActive;

  const NoiseAppliance({
    required this.id,
    required this.name,
    required this.isNoiseActive,
  });

  factory NoiseAppliance.fromJson(Map<String, dynamic> json) {
    return NoiseAppliance(
      id: json['id'] as int? ?? 0,
      name: json['appliance_name'] as String? ?? 'Unknown',
      isNoiseActive: json['is_noise_active'] as bool? ?? false,
    );
  }
}
