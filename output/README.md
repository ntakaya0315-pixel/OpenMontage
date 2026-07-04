# Output

このフォルダには、OpenMontageで生成・編集した成果物を書き出します。

日本語不動産動画の字幕入れ・音量調整では、完成ファイルを `output/subtitled_final.mp4` として作成します。

主な出力ファイル:

- `subtitles.srt` — 自動生成された字幕ファイルです。
- `transcript.json` — 文字起こし確認用のJSONファイルです。
- `subtitled_final.mp4` — 字幕焼き込みと音量正規化済みの完成動画です。

これらの出力ファイルはGitHubにはコミットしません。完成後はCodespacesのファイルエクスプローラーから `output/subtitled_final.mp4` をダウンロードしてください。
