# GitHub Codespacesで日本語不動産動画に字幕と音量調整を入れる手順

この手順は、会社PCにPythonやNode.jsを入れず、GitHub Codespaces上だけで5分〜15分程度の日本語の1人語り不動産動画を処理するためのものです。

## 方針

- 入力動画は `source_media/input.mp4` または `source_media/input.mov` に一時アップロードします。
- 完成動画は `output/subtitled_final.mp4` に書き出します。
- 動画ファイル、字幕ファイル、文字起こしファイル、出力ファイルはGitHubにコミットしません。
- 有料API、追加料金が発生する可能性のあるクラウドサービス、外部生成AIは使いません。
- GitHub Codespacesの無料枠内で動かすことを前提に、無料で使える `faster-whisper` とFFmpegを優先します。
- 初回の文字起こしモデル取得時だけ、Whisperモデルのダウンロードでネットワーク通信が発生します。これは有料API呼び出しではありません。
- 追加コストを避けたい場合は、Codespacesの利用時間・ストレージ上限をGitHub側で確認し、処理後はCodespaceを停止してください。

## 1. Codespacesを開く

1. GitHubでOpenMontageリポジトリを開きます。
2. **Code** → **Codespaces** → **Create codespace on current branch** を選択します。
3. Codespacesのターミナルでリポジトリ直下にいることを確認します。

```bash
pwd
```

## 2. 作業フォルダを確認する

この用途では、以下のフォルダを使います。

```text
OpenMontage/
├── source_media/
│   ├── input.mp4          # Codespaces上に一時アップロードする入力動画（コミットしない）
│   └── input.mov          # MOVの場合はこちらでも可（コミットしない）
├── output/
│   ├── subtitles.srt      # 自動生成される字幕（コミットしない）
│   ├── transcript.json    # 自動生成される文字起こし確認用ファイル（コミットしない）
│   └── subtitled_final.mp4 # 完成後にダウンロードする動画（コミットしない）
└── glossary/
    └── real_estate_terms.txt
```

`source_media/input.mp4` または `source_media/input.mov` はGitHubにコミットしません。Codespacesのファイルエクスプローラーで `source_media/` にドラッグ＆ドロップするか、アップロード機能で配置してください。

## 3. Codespaces内に必要な無料ツールを入れる

会社PCではなくCodespaces内にインストールします。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-subtitles.txt
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-noto-cjk
```

確認します。

```bash
python -c "import faster_whisper; print('faster-whisper ok')"
ffmpeg -version
ffprobe -version
```

## 4. 入力動画を置く

MP4の場合は `source_media/input.mp4`、MOVの場合は `source_media/input.mov` としてCodespaces上にアップロードします。

```bash
test -f source_media/input.mp4 || test -f source_media/input.mov
```

## 5. 1コマンドで字幕入れ・音量アップ・MP4出力を実行する

MP4の場合:

```bash
source .venv/bin/activate
python scripts/subtitle_real_estate_video.py source_media/input.mp4
```

MOVの場合:

```bash
source .venv/bin/activate
python scripts/subtitle_real_estate_video.py source_media/input.mov
```

このスクリプトは以下をまとめて行います。

1. `faster-whisper` で日本語音声をローカル文字起こしします。
2. `glossary/real_estate_terms.txt` の不動産用語をプロンプトと補正候補として使います。
3. 最大2行になるように字幕テキストを整形し、`output/subtitles.srt` を作成します。
4. FFmpegで白文字・黒フチ・画面下部の字幕を焼き込みます。
5. `dynaudnorm` と `loudnorm` で、声の音量差を整え、音割れしにくい範囲でスマホでも聞き取りやすい音量に正規化します。
6. BGMや派手な演出は追加せず、動画の長さを基本的に変えずに `output/subtitled_final.mp4` を作成します。

## 6. 必要に応じて調整する

精度を上げたい場合は `--model medium` を試せます。ただし、CodespacesのCPUとメモリでは処理時間が長くなる場合があります。

```bash
python scripts/subtitle_real_estate_video.py source_media/input.mp4 --model medium
```

字幕サイズを変えたい場合:

```bash
python scripts/subtitle_real_estate_video.py source_media/input.mp4 --font-size 28
```

画質をさらに優先したい場合は、CRFを小さくします。ファイルサイズは大きくなります。

```bash
python scripts/subtitle_real_estate_video.py source_media/input.mp4 --crf 16
```

## 7. 完成動画を確認してダウンロードする

```bash
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 output/subtitled_final.mp4
```

Codespacesのファイルエクスプローラーから `output/subtitled_final.mp4` を右クリックしてダウンロードします。

## 8. コミット前の確認

動画や出力がGitHubに入らないことを確認します。

```bash
git status --short --ignored source_media output
```

`source_media/input.mp4`、`source_media/input.mov`、`output/subtitled_final.mp4`、`output/subtitles.srt`、`output/transcript.json` が `!!` と表示されれば、`.gitignore` により無視されています。

## 注意事項

- この手順は有料APIを使いません。
- OpenAI、ElevenLabs、HeyGenなどの外部APIキーは不要です。
- 外部生成AIやクラウド文字起こしサービスには送信しません。
- GitHub Codespacesの無料枠を超えないよう、長時間処理後はCodespaceを停止してください。
- CodespacesのCPU性能により、文字起こしには動画時間以上の時間がかかる場合があります。
- 出力ファイルは `output/` に作成されますが、動画・字幕・文字起こしファイルはコミットしないでください。
