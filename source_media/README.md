# Source Media

このフォルダには、Codespaces上で一時的に処理する元動画を配置します。

想定ファイル:

- `input.mp4` — MP4形式の元動画ファイルです。
- `input.mov` — MOV形式の元動画ファイルです。

これらの動画ファイルは大きなメディアファイルであり、個人情報を含む可能性もあるため、GitHubにはコミットしません。動画を用意できたら、このフォルダに `input.mp4` または `input.mov` という名前で配置し、処理が終わったら必要に応じてCodespaces上から削除してください。

実行例:

```bash
python scripts/subtitle_real_estate_video.py source_media/input.mp4
```

詳しい手順は `docs/CODESPACES_JA_REAL_ESTATE_SUBTITLES.md` を参照してください。
