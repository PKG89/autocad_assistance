# Configuration: load environment variables from .env (project root) if present.
from pathlib import Path
import os

# Attempt to load a .env file placed at the repository root (one level above
# this package). Use python-dotenv when available, otherwise fall back to a
# tiny parser.
_project_root = Path(__file__).resolve().parents[1]
_env_path = _project_root / ".env"
try:
    from dotenv import load_dotenv  # type: ignore

    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=False)
except Exception:
    if _env_path.exists():
        try:
            with _env_path.open("r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

# Read BOT_TOKEN from environment (possibly populated from .env above)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Templates now live under autocad_assistance/templates
TEMPLATE_BLOCKS_FILE: str = str((Path(__file__).parent / "templates" / "BaseDXF.dxf").resolve())
ADMIN_IDS = os.getenv("ADMIN_IDS", "")  # Замените на реальные ID администраторов
# Основные настройки для импорта точек и построения чертежа
# Цвета задаются согласно стандартной палитре AutoCAD (значения от 1 до 256)
def _parse_admin_ids(value: str | None) -> set[int]:
    if not value:
        return set()
    out: set[int] = set()
    for p in value.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            pass
    return out

# ADMIN_IDS come only from environment (no hardcoded defaults)
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS"))

 # AI-related settings removed (reverted to pre-AI state)

label_colors = {
    "Numbers": 10,      # цвет для подписи номера точки
    "Codes": 200,       # цвет для подписи кода
    "Elevations": 34,   # цвет для подписи высоты
    "Comments": 250     # цвет для подписи комментариев
}

polyline_prefixes = {"k", "gaz", "kabsv", "neft", "Tr", "elkab", "Elkab", "voda", "zab", "brV", "brN", "pod", "Votk", "Notk"}

polyline_layer_mapping = {
    "gaz": "(036) Газопроводы",       # пример: gaz1, gaz2 → Газовая_труба
    "neft": "(014) Нефтепроводы магистральные",     # пример: neft1, neft2 → Нефтяная_труба
    "voda": "(017) ВодоснаБжение",
    # добавляйте здесь любые другие соответствия
}


sm_controller_config = {
    "fields": {
        "point_name": "Номер точки",  # Имя точки
        "x": "x",
        "y": "y",
        "z": "z",
        "code": "code",
        "comment": "коментарий"
    },
    "block_mapping": {
        # Добавляем новую запись для блока Moln (код 109a)
        "Moln": {
            "name": "109a",
            "code": {"moln", "МОЛН"},
            "scale": lambda h: 1.0
        },
        # Добавляем новую запись для блока Fonar (код 110)
        "Fonar": {
            "name": "110",
            "code": {"fonar", "фонар"},
            "scale": lambda h: 1.0
        },
        # Добавляем новую запись для блока TrZn (код 206-1) 
        "TrZn": {
            "name": "206-1",
            "code": {"TrZn", "trzn", "ТрЗн", "GazZn", "gazzn", "укнефть", "уккм"},
            "scale": lambda h: 1.0
        },
        # Добавляем новую запись для блока KIP (код 129-1)
        "KIP": {
            "name": "129-1",
            "code": {"KIP", "skip", "kip", "kik", "KIK", "КИК", "кик", "КИП", "Кип"},
            "scale": lambda h: 1.0
        },
        # Добавляем новую запись для блока Аншлаг (код аншлаг)
        "Аншлаг": {
            "name": "аншлаг",
            "code": {"аншлаг", "Аншлаг", "Anshlag", "anshlag"},
            "scale": lambda h: 1.0
        },
        "Est": {
            "name": "107-1",
            "code": {"est", "Est", "EST", "st est", "st est aroch", "мтэст"},
            "scale": lambda h: 1.0
        },
        "KabZNM": {
            "name": "206-3",
            "code": {"KabZnm", "kabznM", "KABZNM", "КабЗНМ", "кабзнм", "укмет"},
            "scale": lambda h: 1.0
        },
        "KabZNB": {
            "name": "119",
            "code": {"KabZnb", "kabznB", "KABZNB", "КабЗНБ", "кабзнб"},
            "scale": lambda h: 1.0
        },
        "Zadv": {
            "name": "26l",
            "code": {"Zadv", "zadv", "zad", "задв", "Задв", "зад"},
            "scale": lambda h: 1.0
        },
        "Rodnik": {
            "name": "311",
            "code": {"родник", "rodnik", "rod"},
            "scale": lambda h: 1.0
        },
        "Svecha": {
            "name": "091-2",
            "code": {"свеча", "svecha", "svech", "свч", "Свеча", "Свч"},
            "scale": lambda h: 1.0
        },
        "SOD": {
            "name": "Zavod",
            "code": {"СОД", "Sod", "SOD", "сод", "Сод"},
            "scale": lambda h: 1.0
        },
        "СТБ": {
            "name": "1 stb",
            "code": {"стб", "stb", "Stb", "STB"},
            "scale": lambda h: 1.0
        },
        "Колодец Водопровод": {
            "name": "117-2",
            "code": {"КолВод", "KolV", "Водопровод"},
            "scale": lambda h: 1.0
        },
        "Колодец Канализационные сети": {
            "name": "117-3",
            "code": {"КолКан", "KolK", "Канализация"},
            "scale": lambda h: 1.0
        },
        "Колодец Канализационные сети ливневые": {
            "name": "117-4",
            "code": {"KolLiv", "КолЛив", "Ливневка"},
            "scale": lambda h: 1.0
        },
        "Колодец Дренажные трубопроводы": {
            "name": "117-5",
            "code": {"КолДр", "дренаж", "дренажные трубопроводы", "Дренаж"},
            "scale": lambda h: 1.0
        },
        "Колодец Газопроводы": {
            "name": "117-6",
            "code": {"КолГаз", "KolGaz", "KolGAZ"},
            "scale": lambda h: 1.0
        },
        "Колодец Нефтепроводы": {
            "name": "117-7",
            "code": {"Вантуз", "вантуз", "Vantuz"},
            "scale": lambda h: 1.0
        },
        "Колодец Теплотрассы": {
            "name": "117-8",
            "code": {"KolT", "КолТеп", "КолТ"},
            "scale": lambda h: 1.0
        },
        "Колодец Электрокабели": {
            "name": "117-9",
            "code": {"KolEl", "КолЭл"},
            "scale": lambda h: 1.0
        },
        "Колодец Кабели связи": {
            "name": "117-10",
            "code": {"KolSV", "КолСВ", "КолСв"},
            "scale": lambda h: 1.0
        },
        "Колодец Воздухопроводы": {
            "name": "117-11",
            "code": {"КолВозд", "KolVozd"},
            "scale": lambda h: 1.0
        },
        "Колодец Мазутопроводы": {
            "name": "117-12",
            "code": {"KolMaz", "КолМаз"},
            "scale": lambda h: 1.0
        },
        "Колодец Бензопроводы": {
            "name": "117-13",
            "code": {"КолБенз", "KolBenz"},
            "scale": lambda h: 1.0
        },
        "Колодец Золопроводы": {
            "name": "117-14",
            "code": {"KolZol", "КолЗол"},
            "scale": lambda h: 1.0
        },
        "Выход трубы на поверхность": {
            "name": "126",
            "code": {"ОпускТр", "OpyskTr", "Trvzem", "Трвзем"},
            "scale": lambda h: 1.0
        },
        "Трансформаторы на столбах и постаментах ": {
            "name": "113b-2",
            "code": {"Трансформатор", "трансформ", "Transform"},
            "scale": lambda h: 1.0
        },
        "Шкаф": {
            "name": "140-2",
            "code": {"шкаф", "Shkaf", "shkaf"},
            "scale": lambda h: 1.0
        },
        "Дерево": {
            "name": "390-1",
            "code": {"дерево", "Der", "Derevo", "дер", "Дерево"},
            "scale": lambda h: 1.0
        },
        "VL деревянная": {
            "name": "115-7c",
            "code": {"vlDER", "ВлДер"},
            "scale": lambda h: 1.0
        },
        "VL металлическая": {
            "name": "115-7a",
            "code": {"vlMET", "влМЕТ", "ВЛМЕТ"},
            "scale": lambda h: 1.0
        }
    },
    "vl_support": {
        "codes": {"VL", "вл", "ВЛ", "vlGB"},
        "bracing_codes": {"оп", "OP", "vlPODP"},
        "blocks": {
            0: "115-9",
            1: "115-10",
            2: "115-10-2"
        },
        "scale": lambda h: 1.0,
        "distance_threshold": 5.0
    },
    "tower_config": {
        "codes": {"tower", "вышка"},
        "prefixes": {"tower", "вышка"},
        "group_size": 4,
        "min_points": 3,              # допускаем построение по трём точкам (четвёртая восстановится)
        "right_angle_tolerance": 0.05, # относительный допуск при поиске прямого угла (5 %)
        "max_span": 25.0,             # допустимый габарит между точками одной вышки (метры)
        "block_name": "Tower",
        "layer": "Tower",
        "base_width": 1.0,
        "base_height": 1.0,
        "zscale": 1.0,
        "min_scale": 0.01
    },
    "label_colors": label_colors,
    "polyline_prefixes": polyline_prefixes   # добавляем набор префиксов для линий
}


