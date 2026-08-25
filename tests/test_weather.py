"""天气 URL 构建与响应解析测试（不发真实请求）。"""
from urllib.parse import quote

from dafeiyu_pet.services.weather import build_url, parse_weather

SAMPLE = {
    "current_condition": [
        {
            "temp_C": "26",
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


def test_parse_weather():
    temp, desc = parse_weather(SAMPLE)
    assert temp == "26"
    assert desc == "多云"


def test_parse_weather_unknown_desc_kept():
    data = {"current_condition": [{"temp_C": "5", "weatherDesc": [{"value": "Snow"}]}]}
    assert parse_weather(data) == ("5", "Snow")
