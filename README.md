# 說說 ShuoShuo

Windows 語音輸入工具：按一下快捷鍵開始說話、再按一下結束，辨識並潤飾好的繁體中文會自動貼到游標所在的位置（Word、LINE、Gmail、校務系統都可以）。

## 功能

- **口述輸入**：`Ctrl + Alt + 空白鍵` 開始／結束（可在設定修改），或點系統匣圖示
- **辨識**：Gemini（臺灣口音較準）或 Groq（最快）雲端辨識，一個失敗自動換另一個，都不行再用本機 Whisper；小聲的錄音會自動放大
- **AI 潤飾**：去贅字、補標點、處理「不對，是…」這種自我更正；引擎可選 Groq（免費）、Gemini（免費額度）、Claude（付費），額度用完會自動換下一個
- **潤飾風格**：日常、正式公文、電子郵件、條列筆記、親師溝通，也能自訂
- **自訂詞庫**：專有名詞、錯字對照
- **歷史紀錄**：搜尋、複製、換風格重新潤飾
- **會議整理**：現場長時間錄音／匯入錄音檔（mp3、m4a 等）／帶入最近口述 → 產生會議紀錄（摘要、決議、待辦），可存成 Word

## 第一次使用

1. 安裝 `ShuoShuo-Setup-x.x.x.exe`。
   因為安裝檔沒有數位簽章，Windows 可能跳出「Windows 已保護您的電腦」：點「其他資訊」→「仍要執行」。
2. 啟動後會開啟設定，至少填入一把免費的 **Groq** 金鑰：到 [Groq Console](https://console.groq.com/keys) 用 Google 帳號登入 → API Keys → Create API Key
   - 選填 **Gemini**：到 [Google AI Studio](https://aistudio.google.com/apikey) 免費建立（免費方案的內容可能被 Google 用來改進產品）
   - 選填 **Claude**：到 [Anthropic Console](https://console.anthropic.com/settings/keys) 建立（需儲值）
3. 按「測試金鑰」，都打勾就按「儲存」。
4. 在任何文字框點一下，按快捷鍵開始說話，再按一次結束。

說說會常駐在右下角系統匣（橘色麥克風）；右鍵可切換風格、開啟會議整理、歷史紀錄與設定。

## 隱私與資料

- 聲音：Groq 模式會上傳到 Groq 辨識；本機模式完全不外流
- 文字：潤飾時會送到你選的 AI 引擎（Groq、Google 或 Anthropic）
- 金鑰存在 Windows 認證管理員；設定、歷史、錄音存在 `%APPDATA%\ShuoShuo`
- 口述成功後暫存錄音會自動刪除；失敗時保留，可用「會議整理 → 匯入錄音檔」重試
- 涉及學生個資的內容，建議切換為本機辨識並關閉潤飾

## 費用參考

- 只用 Groq：完全免費，有每日用量上限，個人日常使用通常夠用
- Gemini：免費額度內不收費
- Claude：依字數計費，可在 Anthropic Console 設定每月上限

## 開發者

```bash
pip install -r requirements.txt
python run.py          # 執行
python -m pytest tests # 測試
```

推送到 GitHub 的 `main` 分支後，Actions 會自動測試、打包，並把安裝檔發布到 Releases（版本號取自 `shuoshuo/__init__.py`）。
