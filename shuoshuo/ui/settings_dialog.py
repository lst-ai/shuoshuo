"""設定視窗。"""
from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
    QTabWidget, QVBoxLayout, QWidget,
)

from .. import audio, config, hotkey, polish, transcribe
from .worker import run_async


def _hint(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("hint")
    lb.setWordWrap(True)
    lb.setOpenExternalLinks(True)
    return lb


class KeyField(QWidget):
    def __init__(self, name: str):
        super().__init__()
        self.name = name
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(config.get_key(name))
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText("貼上 API key")
        show = QPushButton("顯示")
        show.setCheckable(True)
        show.toggled.connect(
            lambda on: self.edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        lay.addWidget(self.edit, 1)
        lay.addWidget(show)

    def value(self) -> str:
        return self.edit.text().strip()


class SettingsDialog(QDialog):
    saved = Signal()

    def __init__(self, settings: config.Settings, parent=None, welcome: bool = False):
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle("說說 — 設定")
        self.resize(560, 520)
        root = QVBoxLayout(self)
        if welcome:
            lb = QLabel(
                "歡迎使用說說！請先在「API 金鑰」填入免費的 Groq 金鑰（Gemini、Claude 可之後再加），"
                "按「儲存」後就能用快捷鍵開始口述。"
            )
            lb.setWordWrap(True)
            lb.setStyleSheet("background:#FFF3EC;padding:10px;border-radius:6px;")
            root.addWidget(lb)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._tab_general(), "一般")
        self.tabs.addTab(self._tab_keys(), "API 金鑰")
        self.tabs.addTab(self._tab_engine(), "辨識")
        self.tabs.addTab(self._tab_polish(), "潤飾與 AI")
        self.tabs.addTab(self._tab_vocab(), "詞庫")
        if welcome:
            self.tabs.setCurrentIndex(1)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("儲存")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ---------- 分頁 ----------
    def _tab_general(self):
        w = QWidget()
        f = QFormLayout(w)
        self.hotkey = QComboBox()
        self.hotkey.setEditable(True)
        for name, combo in hotkey.PRESETS.items():
            self.hotkey.addItem(name, combo)
        idx = self.hotkey.findData(self.s.hotkey)
        if idx >= 0:
            self.hotkey.setCurrentIndex(idx)
        else:
            self.hotkey.setEditText(self.s.hotkey)
        f.addRow("口述快捷鍵", self.hotkey)
        f.addRow("", _hint("按一下開始錄音、再按一下結束。進階：可直接輸入如 <ctrl>+<shift>+d"))

        self.device = QComboBox()
        self.device.addItem("系統預設麥克風", None)
        try:
            for i, name in audio.list_input_devices():
                self.device.addItem(name, i)
        except Exception:
            pass
        idx = self.device.findData(self.s.input_device)
        self.device.setCurrentIndex(max(0, idx))
        f.addRow("麥克風", self.device)
        mic_row = QHBoxLayout()
        self.mic_btn = QPushButton("測試麥克風（錄 3 秒）")
        self.mic_btn.clicked.connect(self._test_mic)
        self.mic_result = _hint("")
        mic_row.addWidget(self.mic_btn)
        mic_row.addWidget(self.mic_result, 1)
        f.addRow("", mic_row)

        self.sounds = QCheckBox("開始與結束時發出提示音")
        self.sounds.setChecked(self.s.play_sounds)
        f.addRow("", self.sounds)
        self.restore = QCheckBox("貼上後還原原本的剪貼簿內容")
        self.restore.setChecked(self.s.restore_clipboard)
        f.addRow("", self.restore)
        return w

    def _tab_keys(self):
        w = QWidget()
        v = QVBoxLayout(w)
        f = QFormLayout()
        self.groq_key = KeyField("groq")
        self.gemini_key = KeyField("gemini")
        self.claude_key = KeyField("anthropic")
        f.addRow("Groq（必填）", self.groq_key)
        f.addRow("", _hint('語音辨識與潤飾都用得到。到 <a href="https://console.groq.com/keys">Groq Console</a> 免費建立。'))
        f.addRow("Gemini（選填）", self.gemini_key)
        f.addRow("", _hint('到 <a href="https://aistudio.google.com/apikey">Google AI Studio</a> 免費建立。'
                           '注意：免費方案的內容可能被 Google 用來改進產品。'))
        f.addRow("Claude（選填）", self.claude_key)
        f.addRow("", _hint('到 <a href="https://console.anthropic.com/settings/keys">Anthropic Console</a> 建立，需儲值。'))
        v.addLayout(f)
        test = QPushButton("測試金鑰")
        test.clicked.connect(self._test_keys)
        self.test_result = _hint("")
        v.addWidget(test, 0, Qt.AlignLeft)
        v.addWidget(self.test_result)
        v.addWidget(_hint("金鑰存在 Windows 認證管理員，不會寫進一般檔案。"))
        v.addStretch()
        return w

    def _tab_engine(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.eng_gemini = QRadioButton("Gemini 雲端（建議：臺灣口音、中英夾雜較準，稍慢一點）")
        self.eng_groq = QRadioButton("Groq 雲端（最快，Whisper 模型）")
        self.eng_local = QRadioButton("本機 Whisper（離線、聲音不外流，沒有顯卡會比較慢）")
        {"gemini": self.eng_gemini, "groq": self.eng_groq}.get(self.s.engine, self.eng_local).setChecked(True)
        v.addWidget(self.eng_gemini)
        v.addWidget(self.eng_groq)
        v.addWidget(self.eng_local)
        v.addWidget(_hint("雲端引擎失敗時，會先改用另一個已填金鑰的雲端引擎。"))
        self.fallback = QCheckBox("雲端都失敗（沒網路、額度用完）時改用本機")
        self.fallback.setChecked(self.s.fallback_to_local)
        v.addWidget(self.fallback)
        f = QFormLayout()
        self.groq_model = QComboBox()
        self.groq_model.setEditable(True)
        self.groq_model.addItems(["whisper-large-v3", "whisper-large-v3-turbo"])
        self.groq_model.setEditText(self.s.groq_model)
        f.addRow("Groq 辨識模型", self.groq_model)
        self.gemini_stt_model = self._model_combo(
            ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.5-pro"], self.s.gemini_stt_model)
        f.addRow("Gemini 辨識模型", self.gemini_stt_model)
        self.local_model = QComboBox()
        for name, desc in [
            ("tiny", "tiny（最快，準確度低）"),
            ("base", "base（快）"),
            ("small", "small（建議，約 500MB）"),
            ("medium", "medium（較準，約 1.5GB，慢）"),
        ]:
            self.local_model.addItem(desc, name)
        self.local_model.setCurrentIndex(max(0, self.local_model.findData(self.s.local_model)))
        f.addRow("本機模型", self.local_model)
        v.addLayout(f)
        dl = QPushButton("現在下載本機模型")
        dl.clicked.connect(self._download_model)
        self.dl_status = _hint("")
        v.addWidget(dl, 0, Qt.AlignLeft)
        v.addWidget(self.dl_status)
        v.addStretch()
        return w

    def _tab_polish(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.polish_on = QCheckBox("用 AI 潤飾辨識結果（關閉則直接貼上原始辨識文字）")
        self.polish_on.setChecked(self.s.polish_enabled)
        v.addWidget(self.polish_on)
        f = QFormLayout()
        self.style = QComboBox()
        f.addRow("目前風格", self.style)
        self.polish_provider = self._provider_combo(self.s.polish_provider)
        f.addRow("口述潤飾引擎", self.polish_provider)
        self.meeting_provider = self._provider_combo(self.s.meeting_provider)
        f.addRow("會議整理引擎", self.meeting_provider)
        self.provider_fallback = QCheckBox("引擎失敗（額度用完等）時改用其他已填金鑰的引擎")
        self.provider_fallback.setChecked(self.s.provider_fallback)
        f.addRow("", self.provider_fallback)
        self.groq_chat_model = self._model_combo(
            ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"], self.s.groq_chat_model)
        f.addRow("Groq 模型", self.groq_chat_model)
        self.gemini_model = self._model_combo(
            ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview", "gemini-2.5-pro"],
            self.s.gemini_model)
        f.addRow("Gemini 模型", self.gemini_model)
        self.claude_model = self._model_combo(["claude-haiku-5-5", "claude-sonnet-5-5"], self.s.claude_model)
        f.addRow("Claude 口述模型", self.claude_model)
        self.meeting_model = self._model_combo(
            ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"], self.s.claude_meeting_model)
        f.addRow("Claude 會議模型", self.meeting_model)
        v.addLayout(f)

        v.addWidget(QLabel("自訂風格"))
        h = QHBoxLayout()
        self.custom_list = QListWidget()
        self.custom_list.setMaximumWidth(150)
        h.addWidget(self.custom_list)
        right = QVBoxLayout()
        self.custom_name = QLineEdit()
        self.custom_name.setPlaceholderText("風格名稱，例如：校務會議發言")
        self.custom_text = QPlainTextEdit()
        self.custom_text.setPlaceholderText("給 AI 的指示，例如：改寫成適合在校務會議上報告的口吻，條理分明、先講結論。")
        row = QHBoxLayout()
        add = QPushButton("新增／更新")
        rm = QPushButton("刪除")
        row.addWidget(add)
        row.addWidget(rm)
        row.addStretch()
        right.addWidget(self.custom_name)
        right.addWidget(self.custom_text, 1)
        right.addLayout(row)
        h.addLayout(right, 1)
        v.addLayout(h, 1)

        self._custom = dict(self.s.custom_styles)
        self._refresh_styles()
        self.custom_list.currentTextChanged.connect(self._pick_custom)
        add.clicked.connect(self._add_custom)
        rm.clicked.connect(self._remove_custom)
        return w

    def _tab_vocab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("專有名詞（一行一個）"))
        v.addWidget(_hint("人名、校名、計畫名稱等。辨識與潤飾時會優先使用這些寫法。"))
        self.vocab = QPlainTextEdit("\n".join(self.s.vocabulary))
        self.vocab.setPlaceholderText("雲林縣數位學習推動辦公室\nAI人才方舟計畫\n呂舒婷")
        v.addWidget(self.vocab, 1)
        v.addWidget(QLabel("錯字對照（一行一組，用 = 分隔：錯 = 對）"))
        v.addWidget(_hint("辨識老是寫錯的字，直接替換。"))
        self.repl = QPlainTextEdit("\n".join(f"{k} = {val}" for k, val in self.s.replacements.items()))
        self.repl.setPlaceholderText("雲林線 = 雲林縣\n數位學系 = 數位學習")
        v.addWidget(self.repl, 1)
        return w

    @staticmethod
    def _provider_combo(current: str) -> QComboBox:
        c = QComboBox()
        for key, label in [("groq", "Groq（免費）"), ("gemini", "Gemini（免費額度）"), ("claude", "Claude（付費）")]:
            c.addItem(label, key)
        c.setCurrentIndex(max(0, c.findData(current)))
        return c

    @staticmethod
    def _model_combo(items: list[str], current: str) -> QComboBox:
        c = QComboBox()
        c.setEditable(True)
        c.addItems(items)
        c.setEditText(current)
        return c

    # ---------- 動作 ----------
    def _refresh_styles(self):
        cur = self.style.currentText() or self.s.current_style
        self.style.clear()
        self.style.addItems(list(polish.BUILTIN_STYLES) + list(self._custom))
        i = self.style.findText(cur)
        self.style.setCurrentIndex(max(0, i))
        self.custom_list.clear()
        self.custom_list.addItems(list(self._custom))

    def _pick_custom(self, name: str):
        if name in self._custom:
            self.custom_name.setText(name)
            self.custom_text.setPlainText(self._custom[name])

    def _add_custom(self):
        name = self.custom_name.text().strip()
        text = self.custom_text.toPlainText().strip()
        if not name or not text:
            QMessageBox.information(self, "說說", "請填入風格名稱與指示。")
            return
        if name in polish.BUILTIN_STYLES:
            QMessageBox.information(self, "說說", "這個名稱和內建風格重複，請換一個。")
            return
        self._custom[name] = text
        self._refresh_styles()

    def _remove_custom(self):
        name = self.custom_list.currentItem().text() if self.custom_list.currentItem() else ""
        if name in self._custom:
            del self._custom[name]
            self.custom_name.clear()
            self.custom_text.clear()
            self._refresh_styles()

    def _test_keys(self):
        self._store_keys()
        self.test_result.setText("測試中…")

        s = self._collect()
        groq_model = self.groq_model.currentText()

        def job(_p):
            out = []
            if config.get_key("groq"):
                try:
                    import numpy as np

                    tone = (0.1 * np.sin(np.linspace(0, 2000, 16000))).astype("float32")
                    transcribe._groq_chunk(tone, config.get_key("groq"), groq_model, "")
                    out.append("Groq 辨識 ✓")
                except Exception as e:
                    out.append(f"Groq 辨識 ✗ {e}")
            for prov, (name, keyname) in polish.PROVIDERS.items():
                if not config.get_key(keyname):
                    continue
                try:
                    polish.test_provider(prov, s)
                    out.append(f"{name} 潤飾 ✓")
                except Exception as e:
                    out.append(f"{name} 潤飾 ✗ {e}")
            return "\n".join(out) or "請先填入金鑰"

        run_async(job, self.test_result.setText, self.test_result.setText)

    def _test_mic(self):
        device = self.device.currentData()
        self.mic_btn.setEnabled(False)
        self.mic_result.setText("錄音中，請說幾句話…")

        def job(_p):
            import numpy as np
            import sounddevice as sd

            data = sd.rec(int(3 * audio.SAMPLE_RATE), samplerate=audio.SAMPLE_RATE,
                          channels=1, dtype="float32", device=device)
            sd.wait()
            x = data[:, 0]
            peak = audio.peak_level(x)
            name = sd.query_devices(device if device is not None else sd.default.device[0])["name"]
            if not np.any(x):
                verdict = "完全沒有訊號：Windows 可能封鎖了麥克風（設定→隱私權與安全性→麥克風）"
            elif peak < 0.002:
                verdict = "幾乎沒聲音：可能選錯麥克風，或麥克風被靜音"
            elif peak < 0.02:
                verdict = "聲音偏小，可以用，但建議靠近一點或調高音量"
            else:
                verdict = "正常 ✓"
            return f"{name}：{verdict}（音量 {min(100, int(peak * 300))}）"

        def done(msg):
            self.mic_btn.setEnabled(True)
            self.mic_result.setText(msg)

        run_async(job, done, lambda e: done(f"無法錄音：{e}"))

    def _download_model(self):
        name = self.local_model.currentData()
        self.dl_status.setText(f"下載 {name} 中，請稍候（視網速需數分鐘）…")
        run_async(
            lambda _p: transcribe._get_local(name),
            lambda _r: self.dl_status.setText("下載完成 ✓"),
            lambda e: self.dl_status.setText(f"下載失敗：{e}"),
        )

    def _store_keys(self):
        try:
            config.set_key("anthropic", self.claude_key.value())
            config.set_key("groq", self.groq_key.value())
            config.set_key("gemini", self.gemini_key.value())
        except Exception as e:
            QMessageBox.warning(self, "說說", f"無法儲存金鑰：{e}")

    def _collect(self) -> config.Settings:
        s = dataclasses.replace(self.s)  # 先做在副本上，按取消就不影響
        combo = self.hotkey.currentData()
        if self.hotkey.currentText() != hotkey.display_name(combo or ""):
            combo = self.hotkey.currentText().strip()
        s.hotkey = combo or s.hotkey
        s.input_device = self.device.currentData()
        s.play_sounds = self.sounds.isChecked()
        s.restore_clipboard = self.restore.isChecked()
        s.engine = "gemini" if self.eng_gemini.isChecked() else ("groq" if self.eng_groq.isChecked() else "local")
        s.gemini_stt_model = self.gemini_stt_model.currentText().strip() or s.gemini_stt_model
        s.fallback_to_local = self.fallback.isChecked()
        s.groq_model = self.groq_model.currentText().strip() or s.groq_model
        s.local_model = self.local_model.currentData()
        s.polish_enabled = self.polish_on.isChecked()
        s.current_style = self.style.currentText() or "日常"
        s.polish_provider = self.polish_provider.currentData()
        s.meeting_provider = self.meeting_provider.currentData()
        s.provider_fallback = self.provider_fallback.isChecked()
        s.groq_chat_model = self.groq_chat_model.currentText().strip() or s.groq_chat_model
        s.gemini_model = self.gemini_model.currentText().strip() or s.gemini_model
        s.claude_model = self.claude_model.currentText().strip() or s.claude_model
        s.claude_meeting_model = self.meeting_model.currentText().strip() or s.claude_meeting_model
        s.custom_styles = dict(self._custom)
        s.vocabulary = [x.strip() for x in self.vocab.toPlainText().splitlines() if x.strip()]
        repl = {}
        for line in self.repl.toPlainText().splitlines():
            if "=" in line:
                a, b = line.split("=", 1)
                if a.strip():
                    repl[a.strip()] = b.strip()
        s.replacements = repl
        return s

    def _save(self):
        s = self._collect()
        if not hotkey.validate_combo(s.hotkey):
            QMessageBox.warning(self, "說說", f"快捷鍵格式看不懂：{s.hotkey}")
            return
        self._store_keys()
        self.s.__dict__.update(s.__dict__)
        self.s.save()
        self.saved.emit()
        self.accept()
