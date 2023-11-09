# 必要なライブラリとモジュールをインポート
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import pandas
import os
import json
import datetime
import boto3
import uvicorn
import sys
import threading

# 標準入出力ストリームのバッファリングを調整し、kubectl logs時、バッファに溜まらないように設定
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)
sys.stdin = os.fdopen(sys.stdin.fileno(), 'r', buffering=1)

# 出力ディレクトリの設定
output_dir = './output'

# FastAPIのアプリケーションインスタンスを生成
app = FastAPI()

# スレッドクラスの定義


class Thread(threading.Thread):
    """
    スレッドを処理するためのクラス

    Attributes:
        id (str): スレッドID
        input (any): スレッドで処理する入力データ
        output (any): スレッドで生成される出力データ
    """

    def __init__(self, id, input, output, *args, **kwargs):
        """
        コンストラクタ。スレッドのID、入力、出力を初期化

        Args:
            id (str): スレッドID
            input (any): 入力データ
            output (any): 出力データ
        """
        super().__init__(*args, **kwargs)
        self.id = id
        self.input = input
        self.output = output

    def run(self):
        """
        スレッドが実行するメソッド。Excel出力処理を実施
        """
        # スレッドが開始したことを表示
        print(f"Thread ID: {self.id} has started.")

        # 処理開始時間を取得・表示
        now = datetime.datetime.now()
        print("output_to_excel START! " + now.strftime('%Y年%m月%d日%H:%M:%S'))

        # Excel出力関数を呼び出し
        output_to_excel(self.input, self.output)

        # 処理終了時間を取得・表示
        now = datetime.datetime.now()
        print("output_to_excel DONE!  " + now.strftime('%Y年%m月%d日%H:%M:%S'))

        # スレッドが終了したことを表示
        print(f"Thread ID: {self.id} has finished. ")


def output_to_excel(input: str, output: str):
    """
    json形式の入力データをもとに、エクセルファイルを出力する関数。
    出力されたファイルのパーミッションは644とする。

    Args:
        input (str): json形式の文字列。
        output (str): 出力先のファイルパス（パスとファイル名を含む）。
    """

    # 入力が文字列形式ならば、jsonに変換
    if isinstance(input, str):
        input = json.loads(input)

    # jsonファイルの名前を設定して保存
    jsonfilename = output.replace(".xlsx", ".json")
    f = open(jsonfilename, 'w')
    f.write(str(input))
    f.close()

    df = pandas.DataFrame()
    kind_num = 0

    # jsonから必要な情報(kind, apiversion)を取得
    kind = input["kind"].replace("List", "")
    apiversion = input["apiVersion"]

    # アイテムごとにデータフレームを作成・マージ
    for item in input["items"]:
        root_df = df
        df = make_list(item, kind, apiversion)
        kind_num += 1
        if kind_num >= 2:
            df = df_merge(root_df, df, kind_num, kind)

    # 出力先に同名のファイルが存在する場合は書き込みをしない
    if not os.path.isfile(output):
        df = df.reset_index(drop=True)

        # Excelの最初のセルを初期化
        _, max_col = df.shape
        df = df.style.set_properties(
            **{"background-color": "#ffffd1"}).set_properties(
            **{"background-color": "#dddddd"},
            subset=pandas.IndexSlice[:, "key1":"key" + str(max_col - kind_num)])

        # Excelへの書き込み開始時刻をprint
        now = datetime.datetime.now()
        print("df.to_excel START! " + now.strftime('%Y年%m月%d日%H:%M:%S'))

        df.to_excel(output)

        # Excelへの書き込み終了時刻をprint
        now = datetime.datetime.now()
        print("df.to_excel STOP! " + now.strftime('%Y年%m月%d日%H:%M:%S'))

        # ファイルのパーミッションを設定
        os.chmod(output, 0o644)
    else:
        print("出力先にファイルが存在します。")

    # ファイルをMinioにアップロード
    minio_upload(output)
    return


def minio_upload(output):
    """
    指定されたファイルをMinioにアップロードする関数。

    Args:
        output (str): アップロードするファイルのパス（パスとファイル名を含む）。
    """
    # 環境変数(env)からMinioの設定情報を取得
    minio_backet = os.environ.get('MINIO_BACKET')
    minio_endpoint_url = os.environ.get('MINIO_ENDPOINT_URL')
    minio_access_key_id = os.environ.get('MINIO_ACCESS_KEY_ID')
    minio_secret_access_key = os.environ.get('MINIO_SECRET_ACCESS_KEY')

    # boto3を用いてS3クライアントを作成（ここではMinioをS3として扱う）
    s3 = boto3.client(
        's3',
        use_ssl=False,
        endpoint_url=minio_endpoint_url,
        aws_access_key_id=minio_access_key_id,
        aws_secret_access_key=minio_secret_access_key)

    # 既存のバケットをリストアップ
    buckets = s3.list_buckets()["Buckets"]

    # 指定されたバケットが存在するかどうかを確認
    bucket_flag = False
    if len(buckets) > 0:
        for bucket in buckets:
            bucket_name = bucket["Name"]
            if bucket_name == minio_backet:
                bucket_flag = True
                break

    # 指定されたバケットが存在しない場合、新規作成
    if bucket_flag is False:
        s3.create_bucket(Bucket=minio_backet)

    # ファイルをバケットにアップロード
    filename = os.path.basename(output)
    s3.upload_file(output, minio_backet, filename)


def make_list(item, kind, apiversion):
    """
    引数で渡された情報からpandasのDataFrameを作成する関数

    Args:
        item (dict): 処理対象のアイテム
        kind (str): アイテムのk8s kind(種類)を示す文字列
        apiversion (str): アイテムのk8s APIversionを示す文字列
    """
    global current_row_num, key_num, kind_num

    # key_num: 次に新規に追加すべきkeyの番号。既にkey1, key2があればkey_numは3
    key_num = 1
    # current_key_num: 現在のkeyが何階層にあるかを示す(初期は0階層。再帰呼び出しのたびに1階層深くなる)
    current_key_num = 0
    # kind_num 現在何番目のkindかを表す(初期値は1番目のkindを示す)
    kind_num = 1
    # current_row_num: Excelの現在の行番号
    current_row_num = 1

    df = pandas.DataFrame()
    # item内の各キーと値に対して処理を行う
    for k, v_dict in item.items():
        # CRD対応: 一番浅い階層でkeyがapiVersionまたはkindの場合、重複排除のためループをスキップする
        if current_key_num == 0 and (k == "apiVersion" or k == "kind"):
            continue

        # 最初のループでのみ実施されるデータフレームの初期化処理
        if current_row_num == 1:
            # 初期のDataFrameを作成
            df = pandas.DataFrame(
                columns=[
                    'key' + str(key_num),
                    kind + str(kind_num)])
            key_num += 1
            # kind情報をDataFrameに追加
            df, key_num, current_row_num = analyze_nested_list(
                df, "kind", kind, key_num, kind_num, current_row_num,
                current_key_num + 1, -1)
            # apiversion情報をDataFrameに追加
            df, key_num, current_row_num = analyze_nested_list(
                df, "apiVersion", apiversion, key_num, kind_num,
                current_row_num, current_key_num + 1, -1)

        # 毎ループの処理
        df, key_num, current_row_num = analyze_nested_list(
            df, k, v_dict, key_num, kind_num, current_row_num,
            current_key_num + 1, -1)

    return df


def analyze_nested_list(
        df,
        k,
        v_dict,
        key_num,
        kind_num,
        current_row_num,
        current_key_num,
        duplication_num):
    """
    ネストされた辞書やリストを解析して、pandasのDataFrameに情報を追加する

    Args:
        df (DataFrame): 情報を追加する対象のDataFrame
        k (str): 辞書のキー
        v_dict (various): 辞書の値。辞書またはリストであることが多い
        key_num (int): 新しいキーを追加する位置
        kind_num (int): 現在何番目のkindか
        current_row_num (int): DataFrameの現在の行数
        current_key_num (int): 現在処理しているキーの階層
        duplication_num (int): 重複するキーがある場合のカウンタ。無い場合は-1

    Returns:
        df (DataFrame): 更新されたDataFrame
        key_num (int): 更新された新しいキーを追加する位置
        current_row_num (int): 更新されたDataFrameの現在の行数
    """
    # 列を追加するか判定。key_numとcurrent_key_numが一致したら新たな列を追加
    if key_num == current_key_num:
        # 列を追加。既存の行数に合わせて空のデータを作成
        # current_row_num分の配列を作成 (current_row_num=5なら["","","","",""]を作成)
        New_Column = [""] * (current_row_num - 1)
        df.insert(
            loc=current_key_num - 1,
            column='key' + str(key_num),
            value=New_Column)
        # key_numの加算
        key_num += 1

    # 値が文字列、または空の辞書の場合
    if (not isinstance(v_dict, dict) and not isinstance(v_dict, list)) or (
            isinstance(v_dict, dict) and json.dumps(v_dict).startswith('{}')):
        # 新しい行を作成
        New_Column = [""] * (key_num - 1 + kind_num)

        # key, valueをセルへ挿入 ["","",""] -> ["","annotations","testtesttest"]
        # キー名をDataFrameに追加。キー名が重複している場合、"annotations(2)"のように表現
        if duplication_num == -1:
            New_Column[current_key_num - 1] = k
        else:
            New_Column[current_key_num - 1] = k + \
                "(" + str(duplication_num) + ")"

        # 値が無い(None)場合、valueに"null"として追加。値がある場合はその値を追加
        if isinstance(v_dict, type(None)):
            v2 = "null"
        else:
            v2 = v_dict

        # 値をDataFrameに追加
        New_Column[key_num - 1 + kind_num - 1] = v2
        # 新しい行をDataFrameに追加
        s = pandas.Series(New_Column, index=df.columns)
        df = pandas.concat([df, s.to_frame().T], ignore_index=True)
        # 行数を更新
        current_row_num += 1

    # 値が辞書型("{"で始まる)の場合
    elif isinstance(v_dict, dict):
        # この中の処理では、
        # {}のkey, valueの分解のために自身を再帰呼び出し
        # keyをセルに挿入
        for nested_k, nested_v_dict in v_dict.items():
            past_row_num = current_row_num
            # 再帰的にこの関数を呼び出し、key, valueを処理
            df, key_num, current_row_num = analyze_nested_list(
                df, nested_k, nested_v_dict, key_num, kind_num, current_row_num,
                current_key_num + 1, -1)

            # 重複している既存のキーを追加
            for i in range(current_row_num - past_row_num):
                # metadata などの前のkeyをセルに挿入する処理
                if duplication_num == -1:
                    df.iat[current_row_num - 2 - i, current_key_num - 1] = k
                else:
                    df.iat[current_row_num - 2 - i, current_key_num -
                           1] = k + "(" + str(duplication_num) + ")"

    # 値がリスト型("["で始まる)の場合
    elif isinstance(v_dict, list):
        # ここでのnumはリストのforループ回数に応じてカウントし、duplication_numの代わりに扱う
        # (再帰呼び出しした際にannotation(3)のようにkeyを挿入するため)
        num = 1
        # リストの値を取り出して再帰呼び出しやセルへ挿入を行う
        for v_dict2 in v_dict:
            if isinstance(v_dict2, str):
                # 値が文字列の場合: valueがargの場合の特別対応
                # (key: valueではなく、strだけがlistの中に入っているケース)
                if duplication_num == -1:
                    df, key_num, current_row_num = analyze_nested_list(
                        df, k, str(v_dict), key_num, kind_num, current_row_num,
                        current_key_num, -1)
                else:
                    df, key_num, current_row_num = analyze_nested_list(
                        df, k, str(v_dict), key_num, kind_num, current_row_num,
                        current_key_num, duplication_num)
                break

            else:
                for nested_k, nested_v_dict in v_dict2.items():
                    past_row_num = current_row_num
                    # 再帰的にこの関数を呼び出し
                    df, key_num, current_row_num = analyze_nested_list(
                        df, nested_k, nested_v_dict, key_num, kind_num,
                        current_row_num, current_key_num + 1, num)

                    # 重複している既存のキーを追加
                    for i in range(current_row_num - past_row_num):
                        # metadata などの前のkeyをセルに挿入する処理
                        if duplication_num == -1:
                            df.iat[current_row_num - 2 -
                                   i, current_key_num - 1] = k
                        else:
                            df.iat[current_row_num - 2 - i, current_key_num -
                                   1] = k + "(" + str(duplication_num) + ")"
            num += 1
    else:
        print("例外です。タイプは" + type(v_dict))

    return df, key_num, current_row_num


def df_merge(root_df, branch_df, kind_num, kind):
    """
    与えられた2つのDataFrame(root_dfとbranch_df)を特定のキー列を基に結合する
    結合の際に、指定されたキーカラムでマッチしない行は新たに追加される

    Parameters:
    - root_df: pd.DataFrame
        マージされる元となるDataFrame
    - branch_df: pd.DataFrame
        追加・結合するためのDataFrame
    - kind_num: int
        kindの次の列番号
    - kind: str
        追加するkind列の名前の接頭辞

    Returns:
    - pd.DataFrame
        結合後のDataFrame
    """

    # branch_dfの行(row)と列(col)の最大値を取得する
    # ここで取得する列(col)はkey1~x + kind1の合計値 (マージされるbranch_dfのkindは常に1つだけ)
    branch_max_row, branch_max_col = branch_df.shape
    # keyの最大値を出す (kind1のcol分をデクリメント)
    branch_key_num = branch_max_col - 1

    # root_dfの行(row)と列(col)の最大値を取得する
    root_max_row, root_max_col = root_df.shape
    # keyの最大値を出す (kindのcol分をデクリメント)
    root_key_num = root_max_col - kind_num + 1

    # root_dfのkey数(root_key_num)とbranch_dfのkey数(branch_key_num)を比較して、branch_dfの方が大きければ、その分のkey列をroot_dfに追加(手順0)
    if root_key_num < branch_key_num:
        add_key_num = branch_key_num - root_key_num
        for i in range(1, add_key_num + 1):
            root_df.insert(root_key_num - 1 + i, 'key' +
                           str(root_key_num + i), "")
        # root_dfの行と列の最大値を取得する
        root_max_row, root_max_col = root_df.shape

    # kind n+1 の列を追加する(手順1)
    root_df.insert(root_max_col, kind + str(kind_num), "")
    kind_num = kind_num + 1

    # root_dfの行と列の最大値を更新する
    root_max_row, root_max_col = root_df.shape

    # branch_dfの全行を取り出すループ処理
    for branch_row in range(0, branch_max_row):
        # 手順2
        # branch_dfの一行目のkeyを読み込み、root_dfの全行と比較
        # compare_value: branch_dfの特定の行のkeyをまとめて保持する配列
        compare_value = []

        # branch_dfの列ループ(key1 -> key8 -> kind1)
        # 「branch_dfの一行目のkeyを読み込み」の部分
        for branch_col in range(0, branch_key_num):
            # 空白の場合は配列に値を格納しない
            if str(branch_df.iat[branch_row, branch_col]) != "":
                compare_value.append(branch_df.iat[branch_row, branch_col])
            else:
                break

        similar_key_row = -1
        root_match_count = 0
        # root_dfの全行と読み込んだbranch_dfのkeyを比較する処理
        # root_dfの全行のループ処理
        for root_row in range(0, root_max_row):
            # root_df側で一致したkeyの行数を格納する配列
            hit_flag = []
            branch_match_count = 0
            # 取り出した比較すべきすべての列が連続して一致していることを保持するフラグ
            sequential_count = True
            # root_dfの特定の行のkey(列)を取り出すループ処理
            for root_col in range(0, len(compare_value)):
                # root_df側で取り出したkeyとbranch_df側で取り出したkeyを比較する
                if root_df.iat[root_row,
                               root_col] == compare_value[root_col]:
                    hit_flag.append(root_row)
                    if sequential_count:
                        branch_match_count += 1
                else:
                    hit_flag.append(str(-1))
                    sequential_count = False

            # 行の完全一致を示すフラグ
            match_row = True
            # 特定の行の全keyを調べても完全一致しない場合、または不一致のkeyが存在する場合
            if hit_flag.count(root_row) != len(
                    hit_flag) or str(-1) in hit_flag:
                match_row = False

                if branch_match_count >= root_match_count:
                    similar_key_row = root_row
                    root_match_count = branch_match_count
            if match_row:
                # 手順3: root_dfのkind2の当該行のkind2セルにbranch_dfのvalueを入力
                root_df.iat[root_row, root_max_col -
                            1] = branch_df.iat[branch_row, branch_max_col - 1]
                break

        # branch_dfの特定の行を取り出してroot_dfの全行と比較しても一致がない場合
        if not match_row:
            # 手順10
            # 行を挿入する
            similar_key_row += 1
            df1 = root_df[0:similar_key_row].copy()
            df2 = root_df[similar_key_row:]
            padding = [""] * (root_max_col - len(compare_value))
            df1.loc[similar_key_row] = compare_value + padding
            root_df = pandas.concat([df1, df2])

            # kindの値を挿入する
            root_df.iat[similar_key_row, root_max_col -
                        1] = branch_df.iat[branch_row, branch_max_col - 1]

        # root_dfの行と列の最大値を更新する
        root_max_row, root_max_col = root_df.shape

    return root_df


@app.post("/api/v1/resource", response_class=JSONResponse)
async def process_resource(request: Request):
    d = datetime.datetime.now()
    id = request.query_params.get("id")
    filename = id + '-kubereport-' + d.strftime('%y%m%d-%H%M%S')
    output = output_dir + '/' + filename + '.xlsx'

    # ヘッダがjsonでない場合
    content_type = request.headers.get("content-type")
    if content_type != 'application/json':
        print('content type is not application/json {}'.format(content_type))
        return " ", 404

    # 受け取ったjsonをinputデータとして変数に格納
    try:
        input = await request.json()
    except json.JSONDecodeError as e:
        print(sys.exc_info())
        print(e)
        return " ", 406

    # スレッドを動的に作成
    thread = Thread(filename, input, output)
    thread.start()

    return "OK"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
