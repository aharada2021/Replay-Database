# リプレイ処理統合テスト実装計画

作成日: 2026-01-08

## 概要
battle_result_extractor.pyを中心としたリプレイ処理パイプラインの自動テストを実装。
新しく追加した最適化フィールド（matchKey, dateTimeSortable）の検証を含む。

## テスト方針
- **ユニットテスト**: 純粋な関数の検証（モック不要）
- **統合テスト**: S3/DynamoDBをmotoでモックし、E2Eフローを検証
- **テストデータ**: `replays_unpack_upstream/tests/data/random_replays/`の既存リプレイファイル
- **CI/CD**: GitHub Actionsでプッシュ時に自動実行

---

## ディレクトリ構成

```
/tests
  /unit
    test_match_key.py          # matchKey生成、日時フォーマット
    test_battlestats_parser.py # BattleStatsParser変換ロジック
    test_dynamodb_utils.py     # calculate_main_clan_tag等
  /integration
    test_battle_result_extractor.py  # E2E処理フロー
    conftest.py                # pytest fixtures（moto設定）
  conftest.py                  # 共通fixtures
  requirements-test.txt        # テスト依存関係
```

---

## Phase 1: テスト基盤構築

### 1.1 依存関係追加
**ファイル**: `tests/requirements-test.txt`
```
pytest>=7.0.0
pytest-cov>=3.0.0
moto[dynamodb,s3]>=4.0.0
boto3>=1.26.0
```

### 1.2 pytest設定
**ファイル**: `pyproject.toml`（新規作成または追記）
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

### 1.3 共通fixtures
**ファイル**: `tests/conftest.py`
- サンプルDynamoDBレコードのfixture
- サンプルBattleStatsデータのfixture
- リプレイファイルパスのfixture

---

## Phase 2: ユニットテスト

### 2.1 match_key.pyテスト
**ファイル**: `tests/unit/test_match_key.py`

テスト対象:
- `format_sortable_datetime()`: DD.MM.YYYY → YYYYMMDDHHMMSS変換
- `round_datetime_to_5min()`: 5分単位丸め
- `generate_match_key()`: マッチキー生成

```python
def test_format_sortable_datetime_valid():
    assert format_sortable_datetime("08.01.2026 21:56:55") == "20260108215655"

def test_format_sortable_datetime_empty():
    assert format_sortable_datetime("") == "00000000000000"

def test_round_datetime_to_5min():
    assert round_datetime_to_5min("08.01.2026 21:56:55") == "08.01.2026 21:55:00"
    assert round_datetime_to_5min("08.01.2026 21:54:30") == "08.01.2026 21:50:00"

def test_generate_match_key_includes_all_players():
    record = {
        "dateTime": "08.01.2026 21:56:55",
        "mapId": "113",
        "gameType": "clan",
        "ownPlayer": {"name": "Player1"},
        "allies": [{"name": "Player2"}],
        "enemies": [{"name": "Player3"}]
    }
    key = generate_match_key(record)
    assert "Player1" in key
    assert "Player2" in key
    assert "Player3" in key
```

### 2.2 battlestats_parser.pyテスト
**ファイル**: `tests/unit/test_battlestats_parser.py`

テスト対象:
- `BattleStatsParser.to_dynamodb_format()`: フィールド変換
- `BattleStatsParser.parse_player_stats()`: 統計抽出

```python
def test_to_dynamodb_format_converts_keys():
    stats = {"player_name": "Test", "damage": 50000, "hits_ap": 100}
    result = BattleStatsParser.to_dynamodb_format(stats)
    assert result["playerName"] == "Test"
    assert result["damage"] == 50000
    assert result["hitsAP"] == 100

def test_to_dynamodb_format_handles_none():
    stats = {"player_name": None, "damage": None}
    result = BattleStatsParser.to_dynamodb_format(stats)
    assert result["playerName"] == ""
    assert result["damage"] == 0
```

### 2.3 dynamodb utilsテスト
**ファイル**: `tests/unit/test_dynamodb_utils.py`

テスト対象:
- `calculate_main_clan_tag()`: クランタグ集計

```python
def test_calculate_main_clan_tag_most_common():
    players = [
        {"clanTag": "ABC"},
        {"clanTag": "ABC"},
        {"clanTag": "XYZ"}
    ]
    assert calculate_main_clan_tag(players) == "ABC"

def test_calculate_main_clan_tag_empty():
    assert calculate_main_clan_tag([]) is None
```

### 2.4 build_all_players_statsテスト
**ファイル**: `tests/unit/test_battle_result_extractor.py`

テスト対象:
- `build_all_players_stats()`: プレイヤー統計構築

```python
def test_build_all_players_stats_assigns_teams():
    all_stats = {
        "1": {"player_name": "Own", "damage": 100},
        "2": {"player_name": "Ally", "damage": 200},
        "3": {"player_name": "Enemy", "damage": 300}
    }
    record = {
        "ownPlayer": {"name": "Own", "shipId": 1, "shipName": "Ship1"},
        "allies": [{"name": "Ally", "shipId": 2, "shipName": "Ship2"}],
        "enemies": [{"name": "Enemy", "shipId": 3, "shipName": "Ship3"}]
    }
    result = build_all_players_stats(all_stats, record)

    own = next(p for p in result if p["playerName"] == "Own")
    assert own["team"] == "ally"
    assert own["isOwn"] == True

    enemy = next(p for p in result if p["playerName"] == "Enemy")
    assert enemy["team"] == "enemy"
```

---

## Phase 3: 統合テスト

### 3.1 moto fixtures
**ファイル**: `tests/integration/conftest.py`

```python
import pytest
import boto3
from moto import mock_dynamodb, mock_s3

@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-1"

@pytest.fixture
def dynamodb_table(aws_credentials):
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = dynamodb.create_table(
            TableName="wows-replays-test",
            KeySchema=[
                {"AttributeName": "arenaUniqueID", "KeyType": "HASH"},
                {"AttributeName": "playerID", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "arenaUniqueID", "AttributeType": "S"},
                {"AttributeName": "playerID", "AttributeType": "N"}
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        yield table

@pytest.fixture
def s3_bucket(aws_credentials):
    with mock_s3():
        s3 = boto3.client("s3", region_name="ap-northeast-1")
        s3.create_bucket(
            Bucket="wows-replay-bot-test-temp",
            CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"}
        )
        yield s3
```

### 3.2 E2E処理テスト
**ファイル**: `tests/integration/test_battle_result_extractor.py`

```python
import pytest
from pathlib import Path

# テスト用リプレイファイル（完了済み試合）
REPLAY_FILES = list(Path("replays_unpack_upstream/tests/data/random_replays").glob("**/*.wowsreplay"))

@pytest.mark.parametrize("replay_file", REPLAY_FILES[:5])  # 最初の5ファイルでテスト
def test_extract_battle_stats_returns_data(replay_file):
    """BattleStatsパケットが抽出できることを確認"""
    from parsers.battle_stats_extractor import extract_battle_stats

    result = extract_battle_stats(str(replay_file))
    # 完了済み試合ならBattleStatsあり、未完了ならNone
    # どちらもエラーにならないことを確認
    assert result is None or isinstance(result, dict)

def test_optimization_fields_added(dynamodb_table, s3_bucket, sample_replay_file):
    """matchKeyとdateTimeSortableが追加されることを確認"""
    # 1. 初期レコードをDynamoDBに作成
    # 2. S3にリプレイファイルをアップロード
    # 3. battle_result_extractor.handleを呼び出し
    # 4. 更新後のレコードにmatchKey, dateTimeSortableがあることを確認

    # ... 実装詳細

    updated_record = dynamodb_table.get_item(...)
    assert "matchKey" in updated_record["Item"]
    assert "dateTimeSortable" in updated_record["Item"]
    assert updated_record["Item"]["dateTimeSortable"].startswith("2026")
```

---

## Phase 4: CI/CD統合

### 4.1 GitHub Actionsワークフロー更新
**ファイル**: `.github/workflows/deploy.yml`（既存ファイルに追記）

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r tests/requirements-test.txt
          pip install -e src/

      - name: Run tests
        run: |
          cd src && pytest ../tests -v --tb=short
        env:
          REPLAYS_TABLE: wows-replays-test
          SHIP_MATCH_INDEX_TABLE: wows-ship-match-index-test

  deploy:
    needs: test  # テスト成功後にデプロイ
    # ... 既存のデプロイ設定
```

---

## 変更対象ファイル

| ファイル | 操作 | 内容 |
|---------|------|------|
| `tests/requirements-test.txt` | 新規 | テスト依存関係 |
| `tests/conftest.py` | 新規 | 共通fixtures |
| `tests/unit/test_match_key.py` | 新規 | matchKey関連テスト |
| `tests/unit/test_battlestats_parser.py` | 新規 | パーサーテスト |
| `tests/unit/test_dynamodb_utils.py` | 新規 | DynamoDBユーティリティテスト |
| `tests/unit/test_battle_result_extractor.py` | 新規 | build_all_players_statsテスト |
| `tests/integration/conftest.py` | 新規 | moto fixtures |
| `tests/integration/test_battle_result_extractor.py` | 新規 | E2E統合テスト |
| `pyproject.toml` | 新規/更新 | pytest設定 |
| `.github/workflows/deploy.yml` | 更新 | テストジョブ追加 |

---

## 実装順序

1. テスト基盤構築（requirements-test.txt, pyproject.toml, conftest.py）
2. ユニットテスト実装（test_match_key.py, test_battlestats_parser.py, test_dynamodb_utils.py）
3. 統合テスト基盤（integration/conftest.py）
4. 統合テスト実装（test_battle_result_extractor.py）
5. ローカルでテスト実行・修正
6. GitHub Actionsワークフロー更新
7. プッシュしてCI/CDで検証

---

## 検証項目

### ユニットテスト
- [ ] format_sortable_datetime: 正常変換、空文字、不正形式
- [ ] round_datetime_to_5min: 各分単位での丸め
- [ ] generate_match_key: プレイヤー含有、ソート順、5分丸め
- [ ] to_dynamodb_format: キー変換、None処理
- [ ] calculate_main_clan_tag: 最頻値、空リスト
- [ ] build_all_players_stats: チーム割当、isOwnフラグ、ソート順

### 統合テスト
- [ ] extract_battle_stats: リプレイファイルからデータ抽出
- [ ] 最適化フィールド追加: matchKey, dateTimeSortable
- [ ] DynamoDBレコード更新: 旧レコード削除、新レコード作成
- [ ] Ship-Matchインデックス作成

---

## 注意事項

1. **リプレイバージョン**: テストファイルは0.8.0〜13.2.0と古いため、BattleStatsパケットがない（未完了試合）可能性あり
2. **環境変数**: テスト時は`REPLAYS_TABLE=wows-replays-test`を設定
3. **motoの制限**: GSI（GameTypeIndex等）はmotoで完全再現できない場合あり
4. **CI実行時間**: リプレイファイル数を制限（最初の5ファイル等）して高速化
