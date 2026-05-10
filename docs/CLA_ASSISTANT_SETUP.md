# CLA Assistant 導入ガイド

Ripenプロジェクトへの貢献者から法的に有効な同意（署名）を得るために、[CLA Assistant](https://cla-assistant.io/) の導入手順を説明します。

## 準備するもの
- GitHubアカウント（ayato-labs）でログインできること
- プロジェクトのCLAファイルURL: `https://github.com/ayato-labs/ripen/blob/main/CLA.md`

## 導入手順

### 1. サイトへのログイン
1. [CLA Assistant](https://cla-assistant.io/) にアクセスし、`ayato-labs` アカウントで認証します。

### 2. CLAファイルの準備（Gist）
1. [GitHub Gist](https://gist.github.com/) で、ファイル名を `CLA.md` とした新しいGistを作成します。
2. 中身にプロジェクトの [CLA.md](file:///c:/Users/saiha/My_Service/programing/MCP/SharedMemoryServer/CLA.md) の内容をコピーして公開保存します。

### 3. リポジトリの連携
1. CLA Assistantのダッシュボードで **"Configure CLA"** をクリック。
2. 以下の項目を設定：
   - **Repository**: `ayato-labs/ripen` を選択。
   - **Choose a CLA**: ドロップダウンから作成したGist（`CLA.md` または `gistfile1.txt`）を選択。
3. **"Link"** -> **"Yes, let's do this!"** をクリックして完了。

## 導入後の変化
1. **自動コメント**: 外部の人がPRを作成すると、CLA Assistantが自動的に署名を促すコメントをPRに投稿します。
2. **署名ボタン**: 貢献者はコメント内のボタンから、GitHub連携で1クリック署名ができるようになります。
3. **マージ制限**: 署名が完了するまで、GitHub上のステータスチェックが「失敗」となり、マージがブロックされます。

## メリット
- **データベース管理**: 同意したユーザーのリストが `cla-assistant.io` 上に保存され、いつでもエクスポート可能です。
- **商用化への備え**: 後のマネタイズ（商用ライセンス販売）の際、「全てのコードが正当に権利譲渡されていること」を証明する重要な証跡となります。

---
*本ガイドは Ripen プロジェクトの知財保全のために作成されました。*
