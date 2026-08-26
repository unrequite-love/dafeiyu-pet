"""主窗口：桌宠本体（行走/动画/交互/托盘/菜单/AI 对话）。"""
from __future__ import annotations

import ctypes
import logging
import math
import os
import random
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPolygonF, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from dafeiyu_pet.config import PetConfig
from dafeiyu_pet.constants import (
    BASE_SPRITE_H,
    BUBBLE_H,
    ERROR_BUBBLE_SECONDS,
    CLICK_INTERVAL_MS,
    DEFAULT_CITY,
    DRAG_LINES,
    DS_STREAM_BUBBLE_SECONDS,
    DS_STREAM_STEP_CHARS,
    DS_SYSTEM_PROMPT,
    FOOD_LINES,
    INNER_LINES,
    LINES,
    MARGIN,
    MONITOR_MAX_INTERVAL_S,
    MONITOR_MIN_INTERVAL_S,
    REACT_LINES,
    SIZE_LEVELS,
    SPEAK_COOLDOWN_TICKS,
    SPEED,
    TICK_MS,
)
from dafeiyu_pet.logic import bubble_duration, choose_direction, sprite_key
from dafeiyu_pet.paths import APP_DIR, CONFIG_PATH, HISTORY_PATH, PYTHONW, SPRITE_DIR
from dafeiyu_pet.services.deepseek import (
    ChatHistory,
    DeepSeekClient,
    DeepSeekConnectionError,
    DeepSeekError,
    DeepSeekTimeout,
    build_messages,
    truncate_reply,
)
from dafeiyu_pet.services.monitor import clamp_interval, evaluate, read_gpu_temp, read_stats
from dafeiyu_pet.services.weather import fetch_weather
from dafeiyu_pet.ui.chat_dialog import ChatDialog
from dafeiyu_pet.ui.chat_log_dialog import ChatLogDialog
from dafeiyu_pet.ui.food_panel import FoodPanel
from dafeiyu_pet.ui.function_panel import FunctionPanel

logger = logging.getLogger(__name__)


class PetWindow(QWidget):
    """桌宠主窗口。"""

    def __init__(self):
        self.cfg = PetConfig(CONFIG_PATH)

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("topmost", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("大肥鱼桌宠")

        # ---- 精灵加载（缺失则给出明确错误） ----
        self.sprites: dict[tuple[str, int], QPixmap] = {}
        if SPRITE_DIR.exists():
            for mult in SIZE_LEVELS.values():
                h = int(BASE_SPRITE_H * mult)
                for name in ("正面", "侧面", "背面"):
                    sized = SPRITE_DIR / f"{name}_{h}.png"
                    if sized.exists():
                        pix = QPixmap(str(sized))
                    else:
                        pix = QPixmap(str(SPRITE_DIR / f"{name}.png")).scaledToHeight(
                            h, Qt.TransformationMode.SmoothTransformation
                        )
                    self.sprites[(name, h)] = pix
        if not self.sprites:
            raise RuntimeError(f"缺少精灵图资源：{SPRITE_DIR} 不存在或没有可用图片")
        self.icon = QIcon(str(SPRITE_DIR / "icon.png"))

        self.cur_h = int(BASE_SPRITE_H * self.cfg["size"])
        self.win_mx = int(self.cur_h * 0.062) + 6
        self.win_w = (
            max(p.width() for (_name, h), p in self.sprites.items() if h == self.cur_h)
            + self.win_mx * 2
        )
        self.setFixedSize(self.win_w, self.cur_h + BUBBLE_H + MARGIN * 2 + 10)

        # ---- 状态 ----
        mode = self.cfg["mode"]
        self.mode = mode if mode in ("wander", "follow", "still") else "wander"
        self.dir = "down"
        self.facing = 1
        self.target: tuple[float, float] | None = None
        self.rest_until = 0
        self.cur_speed = 0.0
        self.prev_key: tuple[str, int, int] | None = None
        self.cross_t = 0.0
        self.action: str | None = None
        self.action_t = 0.0
        self.eat_t = 0.0
        self.bubble_text = ""
        self.bubble_until = 0.0
        self.bubble_inner = False
        self._wrap_key: tuple | None = None  # 气泡换行缓存键
        self._wrap_lines: list[str] = []  # 气泡换行缓存结果
        self.last_speak_tick = 0
        self.last_system_check = 0
        self.t = 0
        self.jump_t = 0.0
        self.dragging = False
        self.drag_offset: QPoint | None = None
        self.drag_start_pos: QPoint | None = None
        self.last_line = ""

        # ---- AI 相关 ----
        self.ds_busy = False
        self.history = ChatHistory(path=str(HISTORY_PATH))  # 持久化：重启恢复上下文
        self._ds_client: DeepSeekClient | None = None  # 缓存客户端（Session 连接复用）
        self._ds_client_sig: tuple | None = None
        self._say_queue: list[tuple[str, float | None]] = []  # 后台线程 → 主线程的气泡消息队列
        self._main_queue: list = []  # 后台线程 → 主线程的回调队列（弹窗等）

        # ---- 聊天暂停标志 ----
        self.chat_paused = False

        # ---- 功能列表 / 单击双击判定 ----
        self.function_panel = FunctionPanel(self)
        self.food_panel = FoodPanel(self.on_food)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._on_single_click)

        self.chat_dialog = ChatDialog(self)
        self.chat_log = ChatLogDialog(self)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)

        self.bubble_font = QFont("Microsoft YaHei UI", 11)

        # ---- 托盘 ----
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setContextMenu(self._build_menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.right() - self.width() - 80
            y = screen.bottom() - self.height() - 60
        self.move(int(x), int(y))
        self.show()
        self.snap_into_screen()
        if self.cfg.get("passthrough", False):
            self._apply_passthrough(True)

    # ---------- AI ----------
    def _get_ds_client(self, thinking: bool) -> DeepSeekClient:
        """按（key, thinking, 代理）签名缓存客户端，复用底层 Session 连接。"""
        key = self.cfg.get("ds_api_key", "")
        use_proxy = bool(self.cfg.get("use_proxy", True))
        sig = (key, thinking, use_proxy)
        if self._ds_client is None or self._ds_client_sig != sig:
            self._ds_client = DeepSeekClient(key, thinking=thinking, use_proxy=use_proxy)
            self._ds_client_sig = sig
        return self._ds_client

    def call_deepseek(self, user_msg: str) -> None:
        """发送一句话给 DeepSeek，回复经队列回主线程显示。"""
        if self.ds_busy:
            self.say("等等，上一句还没回完呢")
            return
        key = self.cfg.get("ds_api_key", "")
        if not key:
            self.say("请先在右键菜单里设置 DeepSeek Key！")
            return
        # busy 的检查与置位都发生在主线程（UI 事件），无竞态
        self.ds_busy = True
        thinking = bool(self.cfg.get("ds_thinking", False))
        messages = build_messages(DS_SYSTEM_PROMPT, self.history.entries(), user_msg)

        def worker() -> None:
            try:
                # 流式：逐段接收，增量刷新气泡（阅读不等待整句生成完）
                client = self._get_ds_client(thinking)
                parts: list[str] = []
                posted = 0
                for delta in client.chat_stream(messages):
                    parts.append(delta)
                    joined = "".join(parts)
                    if len(joined) - posted >= DS_STREAM_STEP_CHARS:
                        posted = len(joined)
                        self._post(
                            lambda t=joined: self.say(
                                t, duration=DS_STREAM_BUBBLE_SECONDS, force=True
                            )
                        )
                reply = truncate_reply("".join(parts))
                if not reply:
                    raise DeepSeekError("回复为空")
                self.history.append_turn(user_msg, reply)
                self._queue_say(reply)
            except DeepSeekTimeout:
                # 超时/连接失败必须留日志：控制台看不到请求，只能靠本地排查
                logger.warning("DeepSeek 请求超时（thinking=%s）", thinking)
                self._queue_say(
                    "请求超时！右键菜单「测试DS连接」排查", duration=ERROR_BUBBLE_SECONDS
                )
            except DeepSeekConnectionError as e:
                logger.warning("DeepSeek 连接失败（断网/代理/DNS）: %s", e)
                self._queue_say(
                    "连接失败！右键菜单「测试DS连接」排查", duration=ERROR_BUBBLE_SECONDS
                )
            except DeepSeekError as e:
                self._queue_say(f"API错误: {str(e)[:40]}", duration=ERROR_BUBBLE_SECONDS)
            except Exception as e:  # noqa: BLE001 —— 兜底，不让工作线程静默挂掉
                logger.exception("DeepSeek 调用失败")
                self._queue_say(f"请求失败: {str(e)[:40]}", duration=ERROR_BUBBLE_SECONDS)
            finally:
                self.ds_busy = False

        threading.Thread(target=worker, daemon=True).start()

    # ---------- 绘制 ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = self.t * TICK_MS / 1000.0

        if self.bubble_text and now < self.bubble_until:
            if self.bubble_inner:
                bfont = QFont(self.bubble_font)
                bfont.setItalic(True)
                bg, fg = QColor(232, 232, 238, 235), QColor(125, 125, 138)
            else:
                bfont = QFont(self.bubble_font)
                bg, fg = QColor(255, 255, 255, 235), QColor(60, 60, 80)
            fm = QFontMetrics(bfont)
            max_w = min(240, self.width() - 16)
            # 换行结果缓存：气泡驻留期间每个 20ms tick 都会重绘，避免重复逐字测量
            wrap_key = (self.bubble_text, self.bubble_inner, max_w)
            if wrap_key != self._wrap_key:
                lines = []
                cur = ""
                for ch in self.bubble_text:
                    if fm.horizontalAdvance(cur + ch) > max_w - 20:
                        lines.append(cur)
                        cur = ch
                    else:
                        cur += ch
                lines.append(cur)
                self._wrap_key = wrap_key
                self._wrap_lines = lines
            lines = self._wrap_lines
            bw = max(fm.horizontalAdvance(ln) for ln in lines) + 20
            bh = len(lines) * fm.height() + 14
            bx = (self.width() - bw) / 2
            by = 6.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(bx, by, bw, bh), 10, 10)
            tail = QPointF(self.width() / 2, by + bh)
            left_tip = QPointF(tail.x() - 6, tail.y() + 8)
            right_tip = QPointF(tail.x() + 6, tail.y() + 8)
            p.drawPolygon(QPolygonF([tail, left_tip, right_tip]))
            p.setPen(fg)
            p.setFont(bfont)
            for i, ln in enumerate(lines):
                p.drawText(
                    QRectF(bx, by + 7 + i * fm.height(), bw, fm.height()),
                    Qt.AlignmentFlag.AlignCenter,
                    ln,
                )

        # AI 思考中指示：无气泡显示时，头顶冒动态省略号（20ms/帧自动刷新）
        if self.ds_busy and not (self.bubble_text and now < self.bubble_until):
            bfont = QFont(self.bubble_font)
            fm = QFontMetrics(bfont)
            dots = "." * (1 + int(now * 2.5) % 3)
            text = f"💭{dots}"
            tw = fm.horizontalAdvance(text) + 20
            th = fm.height() + 12
            tx = (self.width() - tw) / 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawRoundedRect(QRectF(tx, 8, tw, th), 10, 10)
            p.setPen(QColor(120, 120, 140))
            p.setFont(bfont)
            p.drawText(QRectF(tx, 8, tw, th), Qt.AlignmentFlag.AlignCenter, text)

        cx = self.width() / 2
        walking = self.target is not None and not self.dragging
        if walking:
            sway = math.sin(now * 9.0) * 3.5
            bob = -abs(math.sin(now * 4.5)) * 7.0
        else:
            sway = math.sin(now * 2.5) * 1.5
            bob = 0.0
        breath = 1.0 + 0.02 * math.sin(now * 2.5)
        scale = breath
        jump = -abs(math.sin(self.jump_t * math.pi)) * 14 * self.jump_t if self.jump_t > 0 else 0
        act_rot = act_sx = act_sy = 0.0
        if self.action == "sway":
            act_rot = math.sin(self.action_t * math.pi * 2) * 10 * self.action_t
        elif self.action == "stretch":
            act_sy = 0.06 * math.sin(self.action_t * math.pi)
            act_sx = -0.03 * math.sin(self.action_t * math.pi)
        # 进食动画：整体下压 + 快速咀嚼抖动（底部锚定，脚不离地）
        if self.eat_t > 0:
            eat = math.sin(self.eat_t * math.pi)
            act_sy += (-0.12 + 0.04 * math.sin(now * 12.0)) * eat
            act_sx += 0.07 * eat

        def draw_one(key, opacity):
            if key is None:
                return
            name, h, facing = key
            pix = self.sprites[(name, h)]
            ph = pix.height() * scale * (1 + act_sy)
            pw = pix.width() * scale * (1 + act_sx)
            dx = cx - pw / 2
            bottom = BUBBLE_H + MARGIN + self.cur_h
            dy = bottom - ph + jump + bob
            p.save()
            p.setOpacity(opacity)
            p.translate(cx, bottom)
            p.rotate(sway + act_rot)
            p.translate(-cx, -bottom)
            if facing < 0:
                p.translate(cx, 0)
                p.scale(-1, 1)
                p.translate(-cx, 0)
            p.drawPixmap(QRectF(dx, dy, pw, ph), pix, QRectF(0, 0, pix.width(), pix.height()))
            p.restore()

        cur_key = self._sprite_key()
        if self.cross_t > 0:
            draw_one(self.prev_key, self.cross_t)
            draw_one(cur_key, 1.0 - self.cross_t)
        else:
            draw_one(cur_key, 1.0)

    def _sprite_key(self) -> tuple[str, int, int]:
        return sprite_key(self.dir, self.facing, self.cur_h)

    def _set_dir(self, d: str, facing: int | None = None) -> None:
        if d != self.dir:
            self.prev_key = self._sprite_key()
            self.cross_t = 1.0
            self.dir = d
        if facing is not None and facing != self.facing:
            self.facing = facing

    # ---------- 逻辑 ----------
    def tick(self):
        self.t += 1

        # 后台线程排队的消息统一在主线程处理（线程安全）：气泡 + 主线程回调
        if self._say_queue:
            for text, duration in self._say_queue:
                self.say(text, duration=duration)
            self._say_queue.clear()
        if self._main_queue:
            callbacks, self._main_queue = self._main_queue, []
            for fn in callbacks:
                fn()

        self.check_system_status()

        if self.jump_t > 0:
            self.jump_t = max(0.0, self.jump_t - 0.06)
        if self.eat_t > 0:
            self.eat_t = max(0.0, self.eat_t - 0.03)
        if self.cross_t > 0:
            self.cross_t = max(0.0, self.cross_t - 0.15)
        if self.action_t > 0:
            self.action_t = max(0.0, self.action_t - 0.03)
            if self.action_t == 0:
                self.action = None

        if self.chat_paused or self.dragging:
            self.update()
            return
        now_ms = self.t * TICK_MS

        if self.mode == "follow":
            cursor = self.cursor().pos()
            screen = QApplication.screenAt(cursor) or self.screen() or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            near = (
                self.x() - 100 <= cursor.x() <= self.x() + self.width() + 100
                and self.y() - 100 <= cursor.y() <= self.y() + self.height() + 100
            )
            if near:
                self.target = None
            else:
                tx = max(geo.left(), min(geo.right() - self.width(), cursor.x() - self.width() / 2))
                ty = max(geo.top(), min(geo.bottom() - self.height(), cursor.y() - 90))
                self.target = (tx, ty)
        elif self.mode == "wander":
            if self.target is None:
                if now_ms < self.rest_until:
                    self._maybe_idle_action()
                    self.update()
                    return
                geo = (self.screen() or QApplication.primaryScreen()).availableGeometry()
                self.target = (
                    random.randint(geo.left() + 40, geo.right() - self.width() - 40),
                    random.randint(geo.top() + 40, geo.bottom() - self.height() - 40),
                )
        else:
            self._maybe_idle_action()
            self.update()
            return

        if self.target is not None:
            cx, cy = self.x() + self.width() / 2, self.y() + self.height() / 2
            dx, dy = self.target[0] - cx, self.target[1] - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 12:
                self.target = None
                self.rest_until = self.t * TICK_MS + random.randint(8000, 18000)
                self._set_dir("down")
            else:
                step = self.cur_speed * TICK_MS / 1000.0
                nx, ny = cx + dx / dist * step, cy + dy / dist * step
                self.move(int(nx - self.width() / 2), int(ny - self.height() / 2))
                d, f = choose_direction(dx, dy)
                self._set_dir(d, f)
            if random.random() < 0.002 and self.jump_t == 0:
                self.jump_t = 0.5
        target_speed = SPEED if self.target is not None else 0.0
        self.cur_speed += (target_speed - self.cur_speed) * 0.3
        self.update()

    def _maybe_idle_action(self):
        if random.random() < 0.01:
            pick = random.random()
            if pick < 0.35:
                self.jump_t = 1.0
            elif pick < 0.6:
                self.action, self.action_t = "sway", 1.0
            elif pick < 0.8:
                self.action, self.action_t = "stretch", 1.0
            elif pick < 0.9 and self.t - self.last_speak_tick >= SPEAK_COOLDOWN_TICKS:
                self.last_speak_tick = self.t
                if pick < 0.82:
                    self.say(random.choice(INNER_LINES), inner=True)
                else:
                    self.say(random.choice(LINES))

    def _queue_say(self, text: str, duration: float | None = None) -> None:
        """后台线程调用：只入队，由主线程 tick 统一弹出显示。"""
        self._say_queue.append((text, duration))

    def _post(self, fn) -> None:
        """后台线程调用：把回调排入主线程执行（如弹 QMessageBox）。"""
        self._main_queue.append(fn)

    def say(
        self,
        text: str,
        inner: bool = False,
        duration: float | None = None,
        force: bool = False,
    ) -> None:
        if not force and text == self.last_line and not text.startswith("天气"):
            return
        self.last_line = text
        self.bubble_inner = inner
        self.bubble_text = f"（{text}）" if inner else text
        if duration is None:
            duration = bubble_duration(text)  # 长文本停留更久，给足阅读时间
        self.bubble_until = self.t * TICK_MS / 1000.0 + duration
        self.update()

    def check_system_status(self) -> None:
        # 默认关闭，右键菜单「系统监控」开启后才检测
        if not self.cfg.get("monitor_enabled", False):
            return
        interval_ms = clamp_interval(self.cfg.get("monitor_interval_s")) * 1000
        now = self.t * TICK_MS
        if now - self.last_system_check < interval_ms:
            return
        self.last_system_check = now
        cpu, ram = read_stats()
        msg = evaluate(cpu, ram, read_gpu_temp())
        if msg:
            self.say(msg, duration=bubble_duration(msg))

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.drag_start_pos = e.globalPosition().toPoint()
            self.function_panel.hide()
            self.chat_dialog.hide()
            self.chat_paused = True

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            delta = e.globalPosition().toPoint() - self.drag_start_pos
            if not self.dragging and delta.manhattanLength() > 6:
                self.dragging = True
                self.drag_offset = e.globalPosition().toPoint() - QPoint(self.x(), self.y())
            if self.dragging and self.drag_offset is not None:
                pos = e.globalPosition().toPoint() - self.drag_offset
                self.move(pos)
                if abs(delta.x()) > 10:
                    d, f = choose_direction(delta.x(), 0)
                    self._set_dir(d, f)
                self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.dragging:
                self.dragging = False
                self.drag_offset = None
                self.drag_start_pos = None
                self._set_dir("down", 1)
                self.target = None
                self.rest_until = self.t * TICK_MS + random.randint(6000, 14000)
                if random.random() < 0.5:
                    self.say(random.choice(DRAG_LINES))
                self.chat_paused = False
            else:
                self._click_timer.start(CLICK_INTERVAL_MS)  # 等双击判定
            self.drag_start_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._click_timer.stop()
            self.food_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)

    def _on_single_click(self):
        """单击：蹦跳回嘴 + 弹功能面板。"""
        if random.random() < 0.7:
            self.jump_t = 1.0
        if random.random() < 0.6:
            self.say(random.choice(REACT_LINES))
        panel = self.function_panel
        panel.popup_at(
            self.x() + self.width() / 2 - panel.width() / 2,
            self.y() - panel.height() - 10,
        )

    def on_food(self, food: str) -> None:
        self.food_panel.hide()
        self.eat_t = 1.0
        self.jump_t = 0.6
        self.say(random.choice(FOOD_LINES.get(food, ["好吃！"])))

    def show_chat_dialog(self) -> None:
        if not self.cfg.get("ds_api_key", ""):
            self.say("请先在右键菜单里设置 DeepSeek Key！")
            self.chat_paused = False
            return
        self.chat_dialog.popup_at(
            self.x() + self.width() / 2,
            self.y() + BUBBLE_H,
        )

    def _show_chat_log(self) -> None:
        """回看与 DeepSeek 的完整对话历史（可清空）。"""
        self.chat_log.refresh(self.history.entries())
        self.chat_log.popup_at(self.x() + self.width() / 2, self.y())

    def _set_city_dialog(self) -> None:
        city, ok = QInputDialog.getText(
            self,
            "设置城市",
            "输入城市名:",
            QLineEdit.EchoMode.Normal,
            self.cfg.get("city", DEFAULT_CITY),
        )
        if ok and city.strip():
            self.cfg.set("city", city.strip())
            self.say(f"城市已设置为{city}")

    def _get_weather(self) -> None:
        city = self.cfg.get("city", DEFAULT_CITY)

        def worker() -> None:
            try:
                temp, desc = fetch_weather(city, use_proxy=bool(self.cfg.get("use_proxy", True)))
                self._queue_say(f"{city}今天{temp}°，天气{desc}")
            except Exception as e:  # noqa: BLE001 —— 后台线程兜底
                logger.warning("天气获取失败: %s", e)
                self._queue_say("天气获取失败")

        threading.Thread(target=worker, daemon=True).start()

    # ---------- 菜单 ----------
    def _build_menu(self) -> QMenu:
        m = QMenu(self)
        mode_menu = m.addMenu("模式")
        for label, key in (("自由散步", "wander"), ("跟随鼠标", "follow"), ("原地待着", "still")):
            a = mode_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.mode == key)
            a.triggered.connect(lambda _, k=key: self.set_mode(k))
        size_menu = m.addMenu("大小")
        for label, mult in SIZE_LEVELS.items():
            a = size_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(abs(self.cur_h - BASE_SPRITE_H * mult) < 2)
            a.triggered.connect(lambda _, v=mult: self.set_size(v))
        m.addAction("设置 Key", self._set_key_dialog)
        m.addAction("测试DS连接", self._test_ds_connection)
        m.addAction("聊天记录", self._show_chat_log)
        pxy = m.addAction("使用系统代理")
        pxy.setCheckable(True)
        pxy.setChecked(bool(self.cfg.get("use_proxy", True)))
        pxy.triggered.connect(self._toggle_use_proxy)
        tk = m.addAction("深度思考")
        tk.setCheckable(True)
        tk.setChecked(bool(self.cfg.get("ds_thinking", False)))
        tk.triggered.connect(self._toggle_thinking)
        m.addAction("设置城市", self._set_city_dialog)
        m.addAction("查看天气", self._get_weather)
        m.addSeparator()
        mon = m.addAction("系统监控")
        mon.setCheckable(True)
        mon.setChecked(bool(self.cfg.get("monitor_enabled", False)))
        mon.triggered.connect(self._toggle_monitor)
        m.addAction("监控间隔", self._set_monitor_interval)
        m.addSeparator()
        m.addAction("显示/隐藏", self.toggle_visible)
        m.addAction("回到屏幕内", self.snap_into_screen)
        pa = m.addAction("鼠标穿透（点不到它）")
        pa.setCheckable(True)
        pa.setChecked(self.cfg["passthrough"])
        pa.triggered.connect(lambda on: self.set_passthrough(on))
        ta = m.addAction("窗口置顶")
        ta.setCheckable(True)
        ta.setChecked(self.cfg["topmost"])
        ta.triggered.connect(lambda on: self.set_topmost(on))
        aa = m.addAction("开机自启")
        aa.setCheckable(True)
        aa.setChecked(self.cfg["autostart"])
        aa.triggered.connect(lambda on: self.set_autostart(on))
        m.addSeparator()
        m.addAction("退出", self.quit_app)
        return m

    def _set_key_dialog(self) -> None:
        key, ok = QInputDialog.getText(
            self,
            "设置 DeepSeek Key",
            "输入你的 API Key（从 platform.deepseek.com 获取）:",
            QLineEdit.EchoMode.Password,  # 密文回显，防肩窥
            self.cfg.get("ds_api_key", ""),
        )
        if ok and key.strip():
            key = key.strip()
            self.cfg.set("ds_api_key", key)
            self.say("Key 已保存，验证中…")
            self._verify_key_async(key)
        elif ok and not key.strip():
            self.say("Key 不能为空")

    def _verify_key_async(self, key: str) -> None:
        """保存 Key 后立即 ping 一次，当场发现无效 Key（不发历史）。"""

        def worker() -> None:
            use_proxy = bool(self.cfg.get("use_proxy", True))
            try:
                DeepSeekClient(key, use_proxy=use_proxy).chat(
                    build_messages(DS_SYSTEM_PROMPT, None, "ping")
                )
                self._queue_say("Key 有效，随时开聊！")
            except Exception as e:  # noqa: BLE001 —— 验证入口需兜住一切异常
                logger.warning("Key 验证失败: %r", e)
                self._queue_say(f"Key 验证失败: {str(e)[:40]}", duration=ERROR_BUBBLE_SECONDS)

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_use_proxy(self, on: bool) -> None:
        self.cfg.set("use_proxy", bool(on))
        self.say("已启用系统代理" if on else "已绕过代理，直连模式")

    def _toggle_monitor(self, on: bool) -> None:
        self.cfg.set("monitor_enabled", bool(on))
        if on:
            self.last_system_check = 0  # 立即检测一次，给出即时反馈
            self.say("系统监控已开启，我帮你盯着~")
        else:
            self.say("系统监控已关闭")

    def _set_monitor_interval(self) -> None:
        current = clamp_interval(self.cfg.get("monitor_interval_s"))
        value, ok = QInputDialog.getDouble(
            self,
            "监控间隔",
            "检测间隔（秒，5~3600）:",
            current,
            MONITOR_MIN_INTERVAL_S,
            MONITOR_MAX_INTERVAL_S,
            0,
        )
        if ok:
            self.cfg.set("monitor_interval_s", float(value))
            self.say(f"监控间隔已设为{value:g}秒")

    def _toggle_thinking(self, on: bool) -> None:
        self.cfg.set("ds_thinking", bool(on))
        self.say("开启深度思考，回话要想久一点啦～" if on else "不做脑内小剧场了")

    def _test_ds_connection(self) -> None:
        """诊断：真实发一条消息到 DeepSeek，结果用持久弹窗展示（不靠一闪而过的气泡）。"""
        key = self.cfg.get("ds_api_key", "")
        if not key:
            QMessageBox.information(
                self, "测试DS连接", "还没设置 Key，请先在右键菜单「设置 Key」。"
            )
            return

        self.say("测一下电线…")

        def worker() -> None:
            t0 = time.monotonic()
            try:
                reply = self._get_ds_client(False).chat(
                    build_messages(DS_SYSTEM_PROMPT, None, "ping")
                )
                latency = (time.monotonic() - t0) * 1000
                self._queue_say("连通没问题！")
                self._post(
                    lambda: QMessageBox.information(
                        self, "测试DS连接", f"成功！耗时 {latency:.0f} ms\n模型回复：{reply}"
                    )
                )
            except Exception as e:  # noqa: BLE001 —— 诊断入口需兜住一切异常
                logger.warning("DS 连接测试失败: %r", e)
                self._post(
                    lambda err=e: QMessageBox.warning(
                        self,
                        "测试DS连接",
                        f"失败：{err}\n\n"
                        "排查建议：\n"
                        "1. Key 是否有效（platform.deepseek.com 查看）\n"
                        "2. 是否开了代理/VPN 拦截 api.deepseek.com\n"
                        "3. 详细原因见 logs/pet.log",
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.tray.setContextMenu(self._build_menu())
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visible()

    def contextMenuEvent(self, e):
        self._build_menu().exec(e.globalPos())

    # ---------- 功能 ----------
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.target = None
        self.cfg.set("mode", mode)

    def set_size(self, mult: float) -> None:
        self.cur_h = int(BASE_SPRITE_H * mult)
        self.cfg.set("size", mult)
        self.cross_t = 0.0
        self.prev_key = None
        self.win_mx = int(self.cur_h * 0.062) + 6
        self.win_w = (
            max(p.width() for (_name, h), p in self.sprites.items() if h == self.cur_h)
            + self.win_mx * 2
        )
        self.setFixedSize(self.win_w, self.cur_h + BUBBLE_H + MARGIN * 2 + 10)
        self.snap_into_screen()

    def snap_into_screen(self):
        geo = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        x = max(geo.left(), min(geo.right() - self.width(), self.x()))
        y = max(geo.top(), min(geo.bottom() - self.height(), self.y()))
        self.move(x, y)

    def _apply_passthrough(self, on: bool) -> None:
        hwnd = int(self.winId())
        gwl_exstyle, ws_ex_layered, ws_ex_transparent = -20, 0x80000, 0x20
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, gwl_exstyle)
        style = style | ws_ex_layered
        if on:
            style |= ws_ex_transparent
        else:
            style &= ~ws_ex_transparent
        ctypes.windll.user32.SetWindowLongPtrW(hwnd, gwl_exstyle, style)

    def set_passthrough(self, on: bool) -> None:
        self.cfg.set("passthrough", bool(on))
        self._apply_passthrough(bool(on))
        if on:
            self.say("我隐身了！右键托盘图标解除～")

    def set_topmost(self, on: bool) -> None:
        self.cfg.set("topmost", bool(on))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(on))
        self.show()

    def set_autostart(self, on: bool) -> None:
        self.cfg.set("autostart", bool(on))
        lnk = os.path.join(
            os.environ["APPDATA"],
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
            "Startup",
            "大肥鱼桌宠.lnk",
        )
        try:
            if on:
                if not PYTHONW:
                    raise RuntimeError("找不到 pythonw，无法创建开机自启")
                args = "" if getattr(sys, "frozen", False) else "-m dafeiyu_pet"
                ps = (
                    f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
                    f"$s.TargetPath='{PYTHONW}';$s.Arguments='{args}';"
                    f"$s.WorkingDirectory='{APP_DIR}';$s.Save()"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=True,
                )
                self.say("已开机自启，明天见～")
            else:
                if os.path.exists(lnk):
                    os.remove(lnk)
                self.say("已取消开机自启")
        except Exception as ex:
            logger.warning("设置开机自启失败: %s", ex)
            QMessageBox.warning(self, "开机自启", f"设置失败：{ex}")

    def toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def quit_app(self):
        self.cfg.update(x=self.x(), y=self.y())
        self.tray.hide()
        QApplication.quit()
