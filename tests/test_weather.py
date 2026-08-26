"""天气 URL 构建、响应解析与播报格式测试（不发真实请求）。"""
from urllib.parse import quote

from dafeiyu_pet.services.weather import (
    build_url,
    format_weather,
    pad_cjk_boundaries,
    parse_weather,
)

SAMPLE = {
    "current_condition": [
        {
            "temp_C": "26",
            "weatherCode": "116",
            "weatherDesc": [{"value": "Partly cloudy"}],
        }
    ]
}


def test_build_url_encodes_city():
    url = build_url("汕头")
    assert quote("汕头") in url
    assert url.startswith("https://wttr.in/")
    assert url.endswith("?format=j1")
    assert build_url("New York") == f"https://wttr.in/{quote('New York')}?format=j1"


def test_parse_weather_prefers_code_map():
    # weatherCode=116 → 局部多云（码表优先于英文描述表，同键不同译以码表为准）
    temp, desc = parse_weather(SAMPLE)
    assert temp == "26"
    assert desc == "局部多云"


def test_parse_weather_code_overrides_desc_map():
    data = {
        "current_condition": [
            {"temp_C": "30", "weatherCode": "176", "weatherDesc": [{"value": "Patchy rain nearby"}]}
        ]
    }
    assert parse_weather(data) == ("30", "局部有雨")  # 实测真实场景：码表命中


def test_parse_weather_falls_back_to_desc_map():
    # 无 weatherCode 字段 → 用英文描述表
    data = {
        "current_condition": [
            {"temp_C": "5", "weatherDesc": [{"value": "Light snow"}]}
        ]
    }
    assert parse_weather(data) == ("5", "小雪")


def test_parse_weather_unknown_desc_padded():
    # 码表/描述表都未命中 → 原文保留，中英文边界补空格（不再粘连）
    data = {
        "current_condition": [
            {"temp_C": "1", "weatherDesc": [{"value": "Volcanic ash"}]}
        ]
    }
    assert parse_weather(data) == ("1", "Volcanic ash")
    assert format_weather("深圳", "1", parse_weather(data)[1]) == "深圳今天 1°C，天气Volcanic ash"


def test_format_weather():
    assert format_weather("深圳", "30", "局部有雨") == "深圳今天 30°C，天气局部有雨"
    assert format_weather("北京", "-2", "晴") == "北京今天 -2°C，天气晴"


def test_pad_cjk_boundaries():
    assert pad_cjk_boundaries("今天30C很热") == "今天 30C 很热"
    assert pad_cjk_boundaries("天气Patchy rain") == "天气 Patchy rain"
    assert pad_cjk_boundaries("全部中文无变化") == "全部中文无变化"
    assert pad_cjk_boundaries("all english") == "all english"
