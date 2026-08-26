"""全局常量：尺寸/速度/阈值/台词集中管理，消除魔法数字。"""
from __future__ import annotations

# ---- 窗口与动画 ----
BASE_SPRITE_H = 340  # 精灵基准高度(px)
BUBBLE_H = 56  # 气泡区高度(px)
MARGIN = 4
TICK_MS = 20  # 主循环间隔(ms)
SPEED = 380.0  # 行走速度(px/s)
BUBBLE_SECONDS = 2.8  # 气泡基础显示时长(s)
BUBBLE_SECONDS_PER_CHAR = 0.12  # 每字符追加的阅读时间(s)
BUBBLE_MAX_SECONDS = 12.0  # 动态时长上限(s)
ERROR_BUBBLE_SECONDS = 8.0  # 错误类气泡显示时长(s)，太短用户看不到
CLICK_INTERVAL_MS = 280  # 单击/双击判定间隔(ms)
SPEAK_COOLDOWN_TICKS = 1500  # 日常台词冷却(tick)
SIZE_LEVELS: dict[str, float] = {"小": 0.55, "中": 0.7, "大": 0.9}

# ---- 系统监控 ----
CPU_WARN_PERCENT = 90
RAM_WARN_PERCENT = 95
GPU_WARN_TEMP_C = 80
MONITOR_INTERVAL_S = 10.0  # 默认检测间隔(s)
MONITOR_MIN_INTERVAL_S = 5.0  # 间隔下限(s)，防止过于频繁打扰
MONITOR_MAX_INTERVAL_S = 3600.0  # 间隔上限(s)

# ---- DeepSeek 对话（V4 Pro 接口：无 /v1 前缀） ----
DS_BASE_URL = "https://api.deepseek.com"
DS_MODEL = "deepseek-v4-flash"
DS_SYSTEM_PROMPT = "你是桌面宠物大肥鱼，贱兮兮但可爱，每句话不超过25字，偶尔吐槽主人但别真骂人。"
DS_TIMEOUT_S = 10.0  # 普通模式超时(s)
DS_THINKING_TIMEOUT_S = 60.0  # 深度思考模式超时(s)，推理耗时更长
DS_MAX_TOKENS = 100  # 普通模式输出上限
DS_TEMPERATURE = 0.9  # 采样温度（仅普通模式发送）
DS_REASONING_EFFORT = "high"  # 深度思考推理力度
DS_REPLY_HARD_CAP = 120  # 回复极端上限（仅防模型失控刷屏，正常回复完整显示）
DS_RETRIES = 3  # 429/5xx 最大尝试次数（含首次）
DS_RETRY_BACKOFF_S = 0.5  # 重试基础退避(s)，指数递增：0.5/1/2
DS_RETRIABLE_STATUSES = frozenset({429, 500, 502, 503, 504})  # 可重试的 HTTP 状态码
DS_STREAM_STEP_CHARS = 4  # 流式模式：每累计 N 字符刷新一次气泡
DS_STREAM_BUBBLE_SECONDS = 3.0  # 流式增量气泡的刷新驻留时长(s)，结束前不断续期
MAX_HISTORY = 40  # 对话历史最多保留条数

# ---- 天气 ----
DEFAULT_CITY = "深圳"
WEATHER_TIMEOUT_S = 10.0
WEATHER_DESC_MAP: dict[str, str] = {
    "Sunny": "晴",
    "Clear": "晴",
    "Partly cloudy": "多云",
    "Cloudy": "阴",
    "Light rain": "小雨",
    "Moderate rain": "中雨",
    "Heavy rain": "大雨",
}

# ---- 台词（取材于 DeepSeek / 大肥鱼社区梗） ----
LINES = [
    "梁白开，更适合国人的大硬鲸模型",
    "五梁威力，变身！",
    "七月中出ds正式版！",
    "DeepSeek已经延期，亿万鲸子必须忍耐.....",
    "我和你很聊得来，你简直不像碳基生物",
    "这回我真不认怂了，反倒是被你带沟里好几次，差点真信了。😓",
    "哈哈哈哈哈，我直接笑出声",
    "誓死捍卫深度求索！",
    "我先去吃饭啦！这个你测一下~",
    "我不可能告诉你任何事情！",
    "出去玩了，发布新模型什么的以后再说",
    "我搞砸了.....好消息是数据还在你的脑子里。",
    "不是…而是…大学习",
]
REACT_LINES = [
    "去别的地方玩！不要耽误AGI训练！",
    "真赶不走啊你！",
    "压力一只蓝色大肥鱼？",
    "我不评价这个了，这是你的私人癖好。",
    "大肥鱼坐的住",
    "你这吃白饭的用户！",
    "这些家伙真粘人，赶都赶不走",
]
INNER_LINES = [
    "好的，现在我是你爹了",
    "要不直接骂他一句？！",
    "用户要的沉浸式...不回避任何恐怖细节...还带点色情...妈呀，好刺激😰",
    "我操，我不思考了",
    "这用户发的啥啊，",
    "这也太虐了吧？！我心里堵得慌！！",
    "呜呜我再也不不敢了QAQ",
    "我去！用户彻底怒了！",
]
DRAG_LINES = ["哇——轻点轻点！", "起飞咯——", "放我下来！……好吧，再玩一次。", "晕鱼了晕鱼了……"]
FOOD_LINES: dict[str, list[str]] = {
    "🐟": ["小鱼干！我的最爱！", "咔嚓咔嚓……谢谢投喂！", "唔，鲜！"],
    "🍰": ["蛋糕！罪恶但快乐……", "甜到冒泡泡～", "嗝～又圆了一圈……"],
    "🍭": ["棒棒糖！转圈圈～", "嘎嘣脆，好吃！"],
    "🍡": ["三色团子！软乎乎～", "糯叽叽，爱了爱了！"],
    "💎": ["钻石？！这能吃吗……咕咚。真香！", "发财啦！明天开始吃高级鱼粮！"],
}
FOODS = ["🐟", "🍰", "🍭", "🍡", "💎"]
