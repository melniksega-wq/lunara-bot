import logging
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from kerykeion import AstrologicalSubjectFactory
from kerykeion.chart_data_factory import ChartDataFactory
from matplotlib import patheffects as pe
logger = logging.getLogger(__name__)

CHARTS_DIR = Path(__file__).resolve().parent / "charts"

# Premium palette
BG = "#05050c"
BG_RING = "#0c0c18"
GOLD = "#E8C872"
GOLD_LIGHT = "#FFF1C1"
GOLD_DIM = "#9A7B2f"
GOLD_GLOW = "#FFD966"
MUTED = "#4a4560"
ASPECT_COLORS = {
    "conjunction": "#FFF1C1",
    "opposition": "#E85D75",
    "trine": "#6EC6FF",
    "square": "#FF9F5A",
    "sextile": "#9BE7A8",
}

ZODIAC_SIGNS = ("♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓")
PLANET_SYMBOLS = {
    "Sun": "☉",
    "Moon": "☽",
    "Mercury": "☿",
    "Venus": "♀",
    "Mars": "♂",
    "Jupiter": "♃",
    "Saturn": "♄",
    "Uranus": "♅",
    "Neptune": "♆",
    "Pluto": "♇",
}
PLANET_ORDER = tuple(PLANET_SYMBOLS.keys())
MAJOR_ASPECTS = frozenset({"conjunction", "opposition", "trine", "square", "sextile"})

_CITY_ALIASES: dict[str, tuple[str, str]] = {
    "москва": ("Moscow", "RU"),
    "санкт-петербург": ("Saint Petersburg", "RU"),
    "петербург": ("Saint Petersburg", "RU"),
    "спб": ("Saint Petersburg", "RU"),
    "екатеринбург": ("Yekaterinburg", "RU"),
    "новосибирск": ("Novosibirsk", "RU"),
    "казань": ("Kazan", "RU"),
    "нижний новгород": ("Nizhny Novgorod", "RU"),
    "минск": ("Minsk", "BY"),
    "киев": ("Kyiv", "UA"),
    "київ": ("Kyiv", "UA"),
    "алматы": ("Almaty", "KZ"),
    "астана": ("Astana", "KZ"),
    "тбилиси": ("Tbilisi", "GE"),
    "ереван": ("Yerevan", "AM"),
    "баку": ("Baku", "AZ"),
}

_NATION_ALIASES: dict[str, str] = {
    "россия": "RU",
    "russia": "RU",
    "украина": "UA",
    "ukraine": "UA",
    "беларусь": "BY",
    "belarus": "BY",
    "казахстан": "KZ",
    "kazakhstan": "KZ",
    "грузия": "GE",
    "georgia": "GE",
    "армения": "AM",
    "armenia": "AM",
    "азербайджан": "AZ",
    "azerbaijan": "AZ",
}


def _parse_birth_date(value: str) -> tuple[int, int, int]:
    m = re.match(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*$", value.strip())
    if not m:
        raise ValueError(f"Неверная дата: {value}")
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return y, mo, d


def _parse_birth_time(value: str) -> tuple[int, int]:
    if value.strip().lower() == "неизвестно":
        return 12, 0
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", value.strip())
    if not m:
        raise ValueError(f"Неверное время: {value}")
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError(f"Неверное время: {value}")
    return h, mi


def _resolve_city_nation(place: str) -> tuple[str, str]:
    place = place.strip()
    if "," in place:
        city_part, nation_part = [p.strip() for p in place.split(",", 1)]
    else:
        city_part, nation_part = place, ""

    city_key = city_part.lower()
    if city_key in _CITY_ALIASES:
        return _CITY_ALIASES[city_key]

    nation_key = nation_part.lower()
    nation_code = _NATION_ALIASES.get(
        nation_key, nation_part[:2].upper() if len(nation_part) == 2 else nation_part
    )
    return city_part, nation_code or "RU"


def _lon_to_theta(longitude: float, asc: float) -> float:
    """Асцендент слева, зодиак против часовой стрелки."""
    return np.deg2rad(180.0 + asc - longitude)


def _fetch_chart_data(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    city: str,
    nation: str,
):
    subject = AstrologicalSubjectFactory.from_birth_data(
        name,
        year,
        month,
        day,
        hour,
        minute,
        city=city,
        nation=nation,
        online=True,
        suppress_geonames_warning=True,
    )
    return ChartDataFactory.create_natal_chart_data(subject)


def _collect_planets(subject) -> dict[str, float]:
    planets: dict[str, float] = {}
    for point_name in PLANET_ORDER:
        point = getattr(subject, point_name.lower(), None)
        if point is not None and hasattr(point, "abs_pos"):
            planets[point_name] = float(point.abs_pos)
    return planets


def _collect_houses(subject) -> list[float]:
    cusps: list[float] = []
    for house_name in subject.houses_names_list:
        house = getattr(subject, house_name.lower())
        cusps.append(float(house.abs_pos))
    return cusps


def _render_premium_chart(
    *,
    name: str,
    birth_label: str,
    asc: float,
    planets: dict[str, float],
    house_cusps: list[float],
    aspects: list,
) -> plt.Figure:
    fig = plt.figure(figsize=(10.8, 10.8), facecolor=BG)
    ax = fig.add_subplot(111, polar=True, facecolor=BG)
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1.05)
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines["polar"].set_visible(False)

    # Фоновое свечение
    for r, a in ((1.02, 0.04), (0.88, 0.03), (0.62, 0.02)):
        ax.plot(
            np.linspace(0, 2 * np.pi, 360),
            np.full(360, r),
            color=GOLD_GLOW,
            alpha=a,
            linewidth=2.5,
        )

    # Зодиакальное кольцо — 12 секторов
    for i in range(12):
        start_lon = i * 30.0
        end_lon = (i + 1) * 30.0
        theta1 = _lon_to_theta(start_lon, asc)
        theta2 = _lon_to_theta(end_lon, asc)
        thetas = np.linspace(theta1, theta2, 40)
        r_inner, r_outer = 0.78, 0.98
        fill = "#12122a" if i % 2 == 0 else "#181830"
        ax.fill_between(
            thetas,
            r_inner,
            r_outer,
            color=fill,
            alpha=0.95,
            zorder=1,
        )
        mid_theta = _lon_to_theta(start_lon + 15.0, asc)
        ax.text(
            mid_theta,
            0.89,
            ZODIAC_SIGNS[i],
            ha="center",
            va="center",
            fontsize=22,
            color=GOLD_LIGHT,
            fontweight="bold",
            zorder=5,
            path_effects=[
                pe.withStroke(linewidth=4, foreground=BG, alpha=0.9),
                pe.withStroke(linewidth=8, foreground=GOLD_GLOW, alpha=0.25),
            ],
        )

    # Деления знаков
    for deg in range(0, 360, 30):
        th = _lon_to_theta(float(deg), asc)
        ax.plot([th, th], [0.35, 0.98], color=GOLD_DIM, linewidth=0.9, alpha=0.55, zorder=2)

    # Дома
    for cusp in house_cusps:
        th = _lon_to_theta(cusp, asc)
        ax.plot([th, th], [0.0, 0.76], color=GOLD, linewidth=1.0, alpha=0.45, zorder=2)

    # Декоративные кольца
    for r in (0.76, 0.54, 0.36):
        ax.plot(
            np.linspace(0, 2 * np.pi, 400),
            np.full(400, r),
            color=GOLD_DIM,
            linewidth=0.7,
            alpha=0.35,
            zorder=2,
        )

    # Аспекты
    for aspect in aspects:
        if aspect.aspect not in MAJOR_ASPECTS:
            continue
        if aspect.orbit > 6:
            continue
        p1, p2 = aspect.p1_name, aspect.p2_name
        if p1 not in planets or p2 not in planets:
            continue
        t1 = _lon_to_theta(planets[p1], asc)
        t2 = _lon_to_theta(planets[p2], asc)
        color = ASPECT_COLORS.get(aspect.aspect, GOLD_DIM)
        ax.plot(
            [t1, t2],
            [0.48, 0.48],
            color=color,
            linewidth=1.1,
            alpha=0.35,
            zorder=3,
        )

    # Планеты с glow
    for idx, (pname, lon) in enumerate(planets.items()):
        th = _lon_to_theta(lon, asc)
        r = 0.52 + (idx % 3) * 0.03
        symbol = PLANET_SYMBOLS.get(pname, "●")
        for size, alpha in ((420, 0.07), (280, 0.14), (160, 0.28)):
            ax.scatter(th, r, s=size, c=GOLD_GLOW, alpha=alpha, zorder=6, edgecolors="none")
        ax.text(
            th,
            r,
            symbol,
            ha="center",
            va="center",
            fontsize=15,
            color=GOLD_LIGHT,
            fontweight="bold",
            zorder=7,
            path_effects=[
                pe.withStroke(linewidth=3, foreground=BG),
                pe.withStroke(linewidth=6, foreground=GOLD_GLOW, alpha=0.35),
            ],
        )

    # Центральное свечение
    ax.scatter(0, 0, s=80, c=GOLD_GLOW, alpha=0.12, zorder=4)
    ax.scatter(0, 0, s=25, c=GOLD_LIGHT, alpha=0.5, zorder=4)

    # Подписи
    fig.text(
        0.5,
        0.96,
        "LUNARA",
        ha="center",
        fontsize=11,
        color=GOLD_DIM,
        alpha=0.9,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.08,
        name,
        ha="center",
        fontsize=20,
        color=GOLD_LIGHT,
        fontweight="bold",
        path_effects=[pe.withStroke(linewidth=3, foreground=BG)],
    )
    fig.text(
        0.5,
        0.04,
        birth_label,
        ha="center",
        fontsize=10,
        color=MUTED,
    )

    return fig


def generate_natal_chart_png(
    *,
    telegram_id: int,
    name: str,
    birth_date: str,
    birth_time: str,
    birth_place: str,
) -> Path:
    """Premium натальная карта (matplotlib) → PNG в charts/."""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    year, month, day = _parse_birth_date(birth_date)
    hour, minute = _parse_birth_time(birth_time)
    city, nation = _resolve_city_nation(birth_place)

    chart_data = _fetch_chart_data(name, year, month, day, hour, minute, city, nation)
    subject = chart_data.subject
    asc = float(subject.ascendant.abs_pos)
    planets = _collect_planets(subject)
    house_cusps = _collect_houses(subject)

    birth_label = f"{birth_date} · {birth_time} · {birth_place}"
    fig = _render_premium_chart(
        name=name,
        birth_label=birth_label,
        asc=asc,
        planets=planets,
        house_cusps=house_cusps,
        aspects=chart_data.aspects,
    )

    file_stem = f"chart_{telegram_id}_{year}{month:02d}{day:02d}_{hour:02d}{minute:02d}"
    png_path = CHARTS_DIR / f"{file_stem}.png"
    fig.savefig(
        png_path,
        dpi=150,
        facecolor=BG,
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.15,
    )
    plt.close(fig)
    return png_path
