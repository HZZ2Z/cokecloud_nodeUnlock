#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
CokeCloud Linux 图形客户端 v2 (GTK3, Clash Verge 风格)
=====================================================
- 策略组分区展示(规则模式下每个分流组独立点选,同 Clash Verge)
- 一键连接 / 规则-全局-直连 / TUN 虚拟网卡 / 系统代理
- 组内测速、延迟彩色标注、双击组名测全组
运行: /usr/bin/python3 cokecloud-gui.py
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf  # noqa: E402

import json
import os
import subprocess
import threading
import urllib.parse
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
COKECTL = os.path.join(APP_DIR, "cokectl")
ICON_96 = os.path.join(APP_DIR, "assets", "icon-96.png")
CONF_DIR = os.path.expanduser("~/.config/cokecloud")
CONFIG_JSON = os.path.join(CONF_DIR, "config.json")
RUNTIME_YAML = os.path.join(CONF_DIR, "runtime.yaml")

MODE_LABEL = {"rule": "规则", "global": "全局", "direct": "直连"}

CSS = b"""
.card { border-radius: 8px; padding: 2px; }
.card-selected { border: 2px solid #3584e4; background: rgba(53,132,228,0.14); border-radius: 8px; }
.card-plain { border: 2px solid transparent; border-radius: 8px; }
.big-connect { padding: 8px 22px; }
"""


def cfg():
    try:
        with open(CONFIG_JSON, encoding="utf8") as f:
            return json.load(f)
    except Exception:
        return {}


def rest(method, path, body=None, timeout=8):
    c = cfg()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{c.get('api_port', 9090)}{path}",
        data=data, method=method)
    req.add_header("Authorization", f"Bearer {c.get('secret', '')}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt.strip() else {}
    except Exception:
        return {}


def run_cokectl(*args, timeout=120):
    try:
        p = subprocess.run([COKECTL, *args], capture_output=True,
                           text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 1, "命令超时"
    except Exception as e:
        return 1, str(e)


def ui(fn, *a):
    GLib.idle_add(fn, *a)


def delay_color(d):
    if not d:
        return "#9aa0a6"
    if d < 300:
        return "#26a269"
    if d < 800:
        return "#e5a50a"
    return "#c01c28"


def group_order():
    """从 runtime.yaml 读取策略组顺序(同 Clash 配置顺序)。"""
    try:
        import yaml
        d = yaml.safe_load(open(RUNTIME_YAML, encoding="utf8"))
        return [g["name"] for g in d.get("proxy-groups") or []]
    except Exception:
        return []


class Card(Gtk.Button):
    """节点卡片:延迟点 + 名称。"""

    def __init__(self, name, delay, selected):
        super().__init__(relief=Gtk.ReliefStyle.NONE)
        self.node_name = name
        self.halign = Gtk.Align.FILL
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        dot = Gtk.Label()
        dot.set_markup(f'<span foreground="{delay_color(delay)}">●</span> '
                       f'<span size="8000" foreground="{delay_color(delay)}">'
                       f'{(str(delay) + " ms") if delay else "·"}</span>')
        dot.set_xalign(0)
        lbl = Gtk.Label(label=name)
        lbl.set_xalign(0)
        lbl.set_line_wrap(True)
        lbl.set_line_wrap_mode(2)
        lbl.set_max_width_chars(14)
        lbl.get_style_context().add_class("dim-label" if False else "")
        box.pack_start(dot, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        self.add(box)
        ctx = self.get_style_context()
        ctx.add_class("card")
        ctx.add_class("card-selected" if selected else "card-plain")


class CokeCloudWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="CokeCloud")
        GLib.set_prgname("CokeCloud")
        GLib.set_application_name("CokeCloud")
        self.set_default_size(640, 700)
        try:
            self.set_default_icon_name("cokecloud")
            self.set_default_icon_from_file(ICON_96)
        except Exception:
            pass
        self._testing = False

        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        t = Gtk.Box(spacing=8)
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(ICON_96, 26, 26)
            t.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
        except Exception:
            pass
        lbl = Gtk.Label()
        lbl.set_markup("<b>CokeCloud</b>")
        t.pack_start(lbl, False, False, 0)
        hb.set_custom_title(t)
        self._btn_refresh = Gtk.Button(label="刷新")
        self._btn_refresh.connect("clicked", lambda *_: self.refresh_all())
        hb.pack_end(self._btn_refresh)
        self.set_titlebar(hb)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_border_width(10)
        self.add(root)

        # ---- 控制区
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        root.pack_start(top, False, False, 0)

        self._btn_connect = Gtk.Button(label="连接")
        self._btn_connect.get_style_context().add_class("suggested-action")
        self._btn_connect.get_style_context().add_class("big-connect")
        self._btn_connect.connect("clicked", self.on_connect)
        top.pack_start(self._btn_connect, False, False, 0)

        self._mode_btns = {}
        mb = Gtk.Box(spacing=4)
        for m in ("rule", "global", "direct"):
            b = Gtk.ToggleButton(label=MODE_LABEL[m])
            b.connect("toggled", self.on_mode, m)
            self._mode_btns[m] = b
            mb.pack_start(b, False, False, 0)
        top.pack_start(mb, False, False, 4)
        top.pack_start(Gtk.Label(), True, True, 0)

        tun = Gtk.Box(spacing=6)
        tun.pack_start(Gtk.Label(label="TUN:"), False, False, 0)
        self._sw_tun = Gtk.Switch()
        self._sw_tun.connect("notify::active", self.on_tun)
        tun.pack_start(self._sw_tun, False, False, 0)
        top.pack_start(tun, False, False, 0)

        pr = Gtk.Box(spacing=6)
        pr.pack_start(Gtk.Label(label="系统代理:"), False, False, 0)
        self._sw_proxy = Gtk.Switch()
        self._sw_proxy.connect("notify::active", self.on_proxy)
        pr.pack_start(self._sw_proxy, False, False, 0)
        top.pack_start(pr, False, False, 0)

        # ---- 工具行
        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.pack_start(tools, False, False, 0)
        b1 = Gtk.Button(label="自动优选")
        b1.connect("clicked", lambda *_: self.switch_node("🔰 节点选择", "♻️ 自动选择"))
        tools.pack_start(b1, False, False, 0)
        b2 = Gtk.Button(label="测主组延迟")
        b2.connect("clicked", lambda *_: self.test_group("🔰 节点选择"))
        tools.pack_start(b2, False, False, 0)
        b3 = Gtk.Button(label="测全部组")
        b3.connect("clicked", lambda *_: self.test_all_groups())
        tools.pack_start(b3, False, False, 0)
        b4 = Gtk.Button(label="更新订阅")
        b4.connect("clicked", lambda *_: self.update_sub())
        tools.pack_start(b4, False, False, 0)
        b5 = Gtk.Button(label="出口检测")
        b5.connect("clicked", lambda *_: self.check_exit())
        tools.pack_start(b5, False, False, 0)

        # ---- 策略组区域(Clash Verge 风格)
        self._sections_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_vexpand(True)
        sc.add(self._sections_box)
        root.pack_start(sc, True, True, 0)

        self._status = Gtk.Label(label="未连接")
        self._status.set_xalign(0)
        self._status.set_line_wrap(True)
        root.pack_start(self._status, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.show_all()
        GLib.idle_add(self.refresh_all)

    # ---------- 状态

    def set_status(self, text):
        self._status.set_text(text)

    def set_connect_state(self, connected):
        b = self._btn_connect
        b.set_label("断开" if connected else "连接")
        ctx = b.get_style_context()
        ctx.remove_class("destructive-action" if connected else "suggested-action")
        ctx.add_class("destructive-action" if connected else "suggested-action")

    # ---------- 动作

    def on_connect(self, w):
        connected = bool(rest("GET", "/version").get("version"))
        self._btn_connect.set_sensitive(False)
        if connected:
            self.set_status("断开中 ...")
            threading.Thread(target=self._do_disconnect, daemon=True).start()
        else:
            self.set_status("连接中 ...")
            threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self):
        rc, out = run_cokectl("start", timeout=90)
        if rc != 0:
            ui(self.set_status, out or "启动失败")
            ui(self._btn_connect.set_sensitive, True)
            return
        run_cokectl("proxy", "on", timeout=30)
        ui(self.refresh_all)

    def _do_disconnect(self):
        run_cokectl("proxy", "off", timeout=30)
        rc, out = run_cokectl("stop", timeout=60)
        ui(self.set_status, out or "已断开")
        ui(self.refresh_all)

    def on_mode(self, btn, mode):
        if not btn.get_active():
            return
        for mm, bb in self._mode_btns.items():
            if mm != mode:
                bb.handler_block_by_func(self.on_mode)
                bb.set_active(False)
                bb.handler_unblock_by_func(self.on_mode)
        self.set_status(f"切换为{MODE_LABEL[mode]}模式 ...")
        threading.Thread(target=self._do_mode, args=(mode,), daemon=True).start()

    def _do_mode(self, mode):
        r = rest("PATCH", "/configs", {"mode": mode})
        if isinstance(r, dict) and r.get("__error__"):
            ui(self.set_status, f"模式切换失败: {r}")
            return
        c = cfg()
        c["mode"] = mode
        try:
            with open(CONFIG_JSON, "w", encoding="utf8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        ui(self.refresh_all)

    def on_tun(self, sw, _):
        want = sw.get_active()
        self.set_status("TUN 切换中(首次会弹出授权密码框)...")
        threading.Thread(target=self._do_tun, args=(want,), daemon=True).start()

    def _do_tun(self, want):
        rc, out = run_cokectl("tun", "on" if want else "off", timeout=180)
        ui(self.set_status, (out.splitlines()[-1] if out else "完成"))
        ui(self.refresh_all)

    def on_proxy(self, sw, _):
        want = sw.get_active()
        threading.Thread(target=self._do_proxy, args=(want,), daemon=True).start()

    def _do_proxy(self, want):
        rc, out = run_cokectl("proxy", "on" if want else "off", timeout=40)
        ui(self.set_status, out or "系统代理已设置")

    def update_sub(self):
        self.set_status("更新订阅并合并客户端专用节点 ...")
        threading.Thread(target=self._do_update, daemon=True).start()

    def _do_update(self):
        rc, out = run_cokectl("update", timeout=180)
        ui(self.set_status, out.splitlines()[-1] if out else "完成")
        if rc == 0:
            run_cokectl("restart", timeout=90)
        ui(self.refresh_all)

    def switch_node(self, group, node):
        threading.Thread(target=self._do_switch, args=(group, node),
                         daemon=True).start()

    def _do_switch(self, group, node):
        r = rest("PUT", f"/proxies/{urllib.parse.quote(group)}", {"name": node})
        if isinstance(r, dict) and r.get("__error__"):
            ui(self.set_status, f"切换失败: {r.get('message', r)}")
        else:
            ui(self.set_status, f"{group} → {node}")
        ui(self.refresh_all)

    def on_card_click(self, btn):
        g = btn.group_name
        n = btn.node_name
        if g in ("🎯 全球直连", "⛔ Reject"):
            return
        self.switch_node(g, n)

    # ---------- 测速

    def test_group(self, gname):
        if self._testing:
            return
        self._testing = True
        self.set_status(f"测 {gname} 全组延迟 ...")
        threading.Thread(target=self._do_test_group, args=(gname,),
                         daemon=True).start()

    def _do_test_group(self, gname):
        q = urllib.parse.quote(gname)
        r = rest("GET", f"/proxies/{q}/delay?timeout=3000"
                 "&url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204",
                 timeout=60)
        if isinstance(r, dict) and r.get("__error__"):
            ui(self.set_status, f"测速失败: {r.get('message', r)}")
        else:
            ok_n = len(r) if isinstance(r, dict) else 0
            ui(self.set_status, f"{gname} 测速完成:{ok_n} 个有响应")
        self._testing = False
        ui(self.refresh_all)

    def test_all_groups(self):
        if self._testing:
            return
        self._testing = True
        threading.Thread(target=self._do_test_all, daemon=True).start()

    def _do_test_all(self):
        order = group_order()
        total_ok = 0
        for g in order:
            if g in ("🎯 全球直连", "⛔ Reject"):
                continue
            q = urllib.parse.quote(g)
            r = rest("GET", f"/proxies/{q}/delay?timeout=3000"
                     "&url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204",
                     timeout=90)
            if isinstance(r, dict) and not r.get("__error__"):
                total_ok += len(r)
            ui(self.set_status, f"测速中 ... {g} 完成(累计 {total_ok} 个响应)")
        self._testing = False
        ui(self.set_status, f"全部组测速完成:{total_ok} 个节点有响应")
        ui(self.refresh_all)

    # ---------- 出口检测

    def check_exit(self):
        self.set_status("检测出口 ...")
        threading.Thread(target=self._do_exit, daemon=True).start()

    def _do_exit(self):
        try:
            proxy = urllib.request.ProxyHandler({
                "http": f"http://127.0.0.1:{cfg().get('mixed_port', 7890)}",
                "https": f"http://127.0.0.1:{cfg().get('mixed_port', 7890)}"})
            opener = urllib.request.build_opener(proxy)
            with opener.open("http://ip-api.com/json/?lang=zh-CN"
                             "&fields=status,country,regionName,city,isp,query",
                             timeout=12) as r:
                geo = json.loads(r.read().decode())
            msg = (f"出口: {geo.get('country')} {geo.get('city')} · "
                   f"{geo.get('isp')} · {geo.get('query')}"
                   if geo.get("status") == "success" else "出口查询失败")
        except Exception as e:
            msg = f"出口查询失败: {e}"
        ui(self.set_status, msg)

    # ---------- 主刷新:构建策略组分区

    def refresh_all(self, *_):
        version = rest("GET", "/version").get("version")
        connected = bool(version)
        ui(self.set_connect_state, connected)
        ui(self._btn_connect.set_sensitive, True)
        # TUN/系统代理开关状态同步
        tun_on = bool(cfg().get("tun"))
        for sw, fn, want in ((self._sw_tun, self.on_tun, tun_on),):
            sw.handler_block_by_func(fn)
            sw.set_active(want)
            sw.handler_unblock_by_func(fn)
        try:
            g = subprocess.run(["gsettings", "get", "org.gnome.system.proxy", "mode"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
            proxy_on = g.strip("'\"") == "manual"
        except Exception:
            proxy_on = False
        self._sw_proxy.handler_block_by_func(self.on_proxy)
        self._sw_proxy.set_active(proxy_on)
        self._sw_proxy.handler_unblock_by_func(self.on_proxy)

        # 清空区域
        for child in self._sections_box.get_children():
            self._sections_box.remove(child)

        if not connected:
            self.set_status("未连接 —— 点击「连接」启动(内核 v?)")
            return False

        mode = rest("GET", "/configs").get("mode", "rule")
        for mm, bb in self._mode_btns.items():
            bb.handler_block_by_func(self.on_mode)
            bb.set_active(mm == mode)
            bb.handler_unblock_by_func(self.on_mode)

        proxies = rest("GET", "/proxies").get("proxies", {})
        if mode == "global":
            sections = [("GLOBAL", "Selector")] if "GLOBAL" in proxies else []
        elif mode == "direct":
            lbl = Gtk.Label(label="直连模式:所有流量不经代理,无需选择节点")
            self._sections_box.pack_start(lbl, False, False, 10)
            self._sections_box.show_all()
            self.set_status(f"内核 v{version} · 直连模式")
            return False
        else:
            order = group_order()
            sections = [(g, proxies[g].get("type")) for g in order if g in proxies]

        for gname, gtype in sections:
            ginfo = proxies.get(gname) or {}
            members = ginfo.get("all") or []
            now = ginfo.get("now")
            self._sections_box.pack_start(
                self._build_section(gname, gtype, members, now, proxies),
                False, False, 0)
        self._sections_box.show_all()
        now_main = proxies.get("🔰 节点选择", {}).get("now", "?")
        self.set_status(f"内核 v{version} · {MODE_LABEL.get(mode, mode)}模式 · "
                        f"主节点: {now_main}")
        return False

    def _build_section(self, gname, gtype, members, now, proxies):
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_border_width(6)

        # 头部:组名 + 类型 + 测速按钮 + 当前值
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_lbl = Gtk.Label()
        typ = {"Selector": "手动", "URLTest": "自动",
               "Fallback": "故障转移", "LoadBalance": "负载"}.get(gtype, gtype)
        name_lbl.set_markup(f"<b>{gname}</b> "
                            f'<span size="8000" foreground="#777">({typ} · '
                            f'{len(members)} 项)</span>')
        name_lbl.set_xalign(0)
        head.pack_start(name_lbl, False, False, 0)
        head.pack_start(Gtk.Label(), True, True, 0)
        if gname not in ("🎯 全球直连", "⛔ Reject"):
            tb = Gtk.Button(label="测速")
            tb.set_relief(Gtk.ReliefStyle.NONE)
            tb.connect("clicked", lambda *_: self.test_group(gname))
            head.pack_end(tb, False, False, 0)
        box.pack_start(head, False, False, 0)

        # 节点卡片流式布局
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_min_children_per_line(2)
        flow.set_max_children_per_line(6)
        for n in members:
            info = proxies.get(n, {})
            hist = info.get("history") or []
            d = hist[-1].get("delay") if hist else None
            card = Card(n, d, n == now)
            card.group_name = gname
            card.connect("clicked", self.on_card_click)
            flow.add(card)
        box.pack_start(flow, False, False, 0)
        frame.add(box)
        return frame


if __name__ == "__main__":
    GLib.set_prgname("CokeCloud")
    GLib.set_application_name("CokeCloud")
    w = CokeCloudWindow()
    Gtk.main()
