# 残タスク
## 非機能面
- slash commandで起動するlambda関数は、メッセージを返して終わりなので、memoryを小さくする。
- リプレイ処理用のlambda関数は現在3008MB割り当ててあるが、実行リソースとして必要なmemoryサイズにサイジングする。できれば小さくしたい。
## 機能面
- リプレイファイルに含まれるgameTypeに応じて投稿先のdiscordチャンネルを変更する。具体的には ClanBattleの場合には、clan_戦士の道 のようなチャンネルに投稿されるようにしたい。　他のgameTypeとして、　RandomBattle, RankBattleがある。 おそらくそのためにはmap_names.yamlを多少変更する必要がある。
## 管理面
- ファイルを関心ごとに分離して保存したい。 deploy, src, docs　のような階層構造で分離したい。
