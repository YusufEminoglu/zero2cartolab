# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Solar Position & Architectural Lighting Engine for 2.5D Cartography.

Calculates astronomical solar altitude and azimuth from latitude, day of year,
and time of day using the Spencer/NOAA solar position algorithm, translating them
into realistic 2.5D building extrusion lighting angles, shadow lengths, and facade shades.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

# Seasonal day-of-year presets
SOLAR_SEASONS = {
    "summer_solstice": 172,   # June 21
    "spring_equinox": 80,     # March 21
    "equinox": 80,            # March 21 / Sept 23
    "autumn_equinox": 266,    # Sept 23
    "winter_solstice": 355,   # Dec 21
}

# Time-of-day presets (in 24-hour decimal)
SOLAR_TIMES = {
    "dawn_crisp": 7.0,        # 07:00 - dramatic low eastern sun, long shadows
    "morning_crisp": 9.0,     # 09:00 - eastward shadows, crisp facade contrast
    "midday_zenith": 12.5,    # 12:30 - high sun, bright roofs, short crisp shadows
    "afternoon_studio": 15.0, # 15:00 - classic architectural presentation lighting
    "golden_hour": 17.5,      # 17:30 - warm low sun, dramatic shadows
    "twilight_dusk": 19.0,    # 19:00 - deep low sun angle
}


def calculate_solar_position(
    latitude_deg: float,
    day_of_year: int = 172,
    solar_hour: float = 15.0,
) -> Tuple[float, float]:
    """
    Calculate solar altitude angle (elevation above horizon in degrees)
    and solar azimuth angle (clockwise from North in degrees).
    """
    lat_rad = math.radians(latitude_deg)

    # Solar declination angle delta
    decl_deg = 23.45 * math.sin(math.radians((360.0 / 365.0) * (284 + day_of_year)))
    decl_rad = math.radians(decl_deg)

    # Hour angle H in radians (15 deg per hour from noon)
    hour_angle_deg = 15.0 * (solar_hour - 12.0)
    hour_angle_rad = math.radians(hour_angle_deg)

    # Solar altitude alpha
    sin_alt = math.sin(lat_rad) * math.sin(decl_rad) + math.cos(lat_rad) * math.cos(decl_rad) * math.cos(hour_angle_rad)
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt_rad = math.asin(sin_alt)
    alt_deg = max(0.0, math.degrees(alt_rad))

    # Solar azimuth theta (clockwise from North)
    if alt_deg >= 89.9:
        azimuth_deg = 180.0
    else:
        cos_az = (math.sin(decl_rad) - math.sin(alt_rad) * math.sin(lat_rad)) / max(1e-6, (math.cos(alt_rad) * math.cos(lat_rad)))
        cos_az = max(-1.0, min(1.0, cos_az))
        az_raw = math.degrees(math.acos(cos_az))
        if hour_angle_deg > 0:
            azimuth_deg = 360.0 - az_raw
        else:
            azimuth_deg = az_raw

    return (round(alt_deg, 2), round(azimuth_deg % 360.0, 2))


def solar_to_25d_lighting(
    latitude_deg: float = 38.4,
    season: str = "equinox",
    time_preset: str = "afternoon_studio",
) -> Dict[str, any]:
    """
    Convert solar coordinates into QGIS 2.5D building extrusion parameters:
    extrusion angle (degrees), roof illumination factor, wall shading factors,
    and shadow length coefficient.
    """
    day_num = SOLAR_SEASONS.get(season.lower(), 80)
    hour = SOLAR_TIMES.get(time_preset.lower(), 15.0)

    alt_deg, az_deg = calculate_solar_position(latitude_deg, day_num, hour)

    # Extrusion rendering angle (opposite to shadow or aligned to light source)
    # QGIS 2.5D style defaults: angle ~ 70 deg, roof_factor ~ 1.0, wall ~ 0.7-0.85
    shadow_angle = (az_deg + 180.0) % 360.0

    # Shadow length multiplier: cotangent of altitude (clamped for aesthetic stability)
    if alt_deg > 5.0:
        shadow_len_mult = round(1.0 / math.tan(math.radians(alt_deg)), 2)
    else:
        shadow_len_mult = 5.0
    shadow_len_mult = max(0.2, min(3.5, shadow_len_mult))

    # Facade luminance factors based on altitude
    roof_lum = round(max(0.6, min(1.0, math.sin(math.radians(alt_deg)) * 1.15)), 2)
    wall_lum = round(max(0.4, min(0.9, math.cos(math.radians(alt_deg)) * 0.9)), 2)

    return {
        "solar_altitude_deg": alt_deg,
        "solar_azimuth_deg": az_deg,
        "shadow_angle_deg": round(shadow_angle, 1),
        "shadow_length_mult": shadow_len_mult,
        "roof_luminance": roof_lum,
        "wall_luminance": wall_lum,
        "description": f"{time_preset.replace('_', ' ').title()} (Sun Elev: {alt_deg}°, Azimuth: {az_deg}°)",
    }


def calculate_solar_shading_contrast(
    altitude_deg: float,
    azimuth_deg: float,
    aspect_deg: float = 135.0,
    slope_deg: float = 0.0,
) -> float:
    """
    Calculate Lambertian diffuse shading factor in [0.0, 1.0] for a terrain or building facet
    given sun position and surface aspect/slope.
    """
    alt_rad = math.radians(altitude_deg)
    az_rad = math.radians(azimuth_deg)
    asp_rad = math.radians(aspect_deg)
    slp_rad = math.radians(slope_deg)

    # Lambert cosine law for arbitrary surface
    cos_inc = (
        math.sin(alt_rad) * math.cos(slp_rad)
        + math.cos(alt_rad) * math.sin(slp_rad) * math.cos(az_rad - asp_rad)
    )
    return round(max(0.0, min(1.0, cos_inc)), 4)


def calculate_shadow_vector(
    altitude_deg: float,
    azimuth_deg: float,
    height: float = 10.0,
) -> Tuple[float, float, float]:
    """
    Compute shadow ground offset vector (dx, dy, total_length) for an object of given height.
    """
    if altitude_deg <= 1.0:
        length = height * 10.0
    else:
        length = height / math.tan(math.radians(altitude_deg))

    # Shadow direction is opposite to sun azimuth
    shadow_az_rad = math.radians((azimuth_deg + 180.0) % 360.0)
    dx = length * math.sin(shadow_az_rad)
    dy = length * math.cos(shadow_az_rad)
    return (round(dx, 2), round(dy, 2), round(length, 2))
