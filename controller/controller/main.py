from kubernetes import client, config, watch
import os
import sys
import threading
import time
import datetime
import requests
import re
from requests.exceptions import Timeout

# 標準出力、標準エラー出力、標準入力のバッファリングを調整
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)
sys.stdin = os.fdopen(sys.stdin.fileno(), 'r', buffering=1)


class StoppableThread(threading.Thread):
    """
    このクラスはスレッドを生成して、Kubernetesのカスタムリソース（CRD）を監視し
    変化があった場合にはaggregatorから情報を取得 -> formatterにてエクセルへ書き出し
    の指示を行う

    :param id: スレッドID
    :param kubeAggregatorURL: kube-aggregatorのURL
    :param kubeFormatterURL: kube-formatterのURL
    :param ns: 対象とする名前空間
    :param kind: リソースの種類
    :param minutes: ポーリング間隔（分）
    :param group: APIグループ
    :param namespace: 名前空間
    :param version: APIバージョン
    :param plural: リソースの複数形
    :param name: リソース名
    :param obj: カスタムリソースオブジェクト
    :param api: Kubernetes APIクライアント
    """
    # コンストラクタ

    def __init__(
            self,
            id,
            kubeAggregatorURL,
            kubeFormatterURL,
            ns,
            kind,
            minutes,
            group,
            namespace,
            version,
            plural,
            name,
            obj,
            api,
            *args,
            **kwargs):
        # スレッドの基本設定を初期化
        super().__init__(*args, **kwargs)
        # 各種パラメータの設定
        self.id = id
        self.kubeAggregatorURL = kubeAggregatorURL
        self.kubeFormatterURL = kubeFormatterURL
        self.ns = ns
        self.kind = kind
        self.minutes = minutes
        self.group = group
        self.namespace = namespace
        self.version = version
        self.plural = plural
        self.name = name
        self.obj = obj
        self.api = api
        # スレッド停止用のイベントオブジェクト
        self._stop_event = threading.Event()

    def init_spreadsheet(self, obj):
        """
        スプレッドシートオブジェクトの初期化を行う。
        :param obj: スプレッドシートオブジェクト
        :return: 初期化されたスプレッドシートオブジェクト
        """
        # 初期化済みかチェック
        if 'status' in obj:
            return obj

        # statusフィールドを初期化
        d = {
            'status':
                {
                    'aggregated':
                    {
                        'error': 'N/A',
                        'startedAt': 'N/A',
                        'success': 'N/A',
                        'updateAt': 'N/A'
                    },
                    'formatted':
                    {
                        'error': 'N/A',
                        'startedAt': 'N/A',
                        'success': 'N/A',
                        'updateAt': 'N/A'
                    },
                    'friendlyDescription': 'N/A'
                }
        }
        obj |= d
        return obj

    def stop(self):
        """
        スレッドを停止するイベントをセットする。
        """
        self._stop_event.set()

    def stopped(self):
        """
        スレッドが停止しているかどうかを返す。

        :return: スレッドが停止しているかどうか（真偽値）
        """
        return self._stop_event.is_set()

    def run(self):
        """
        スレッドが実行する主要な処理

        この関数内でCRDに対する各種操作を実施
        """
        # スレッドの開始を報告
        print(f"Thread ID: {self.id} has started.")
        # スプレッドシートオブジェクトの初期化
        obj = self.obj
        obj = self.init_spreadsheet(obj)

        # 最初のループであるかのフラグ
        firstCycleFlg = True

        # スレッド停止イベントがセットされるまでループ
        while not self.stopped():
            # スレッド動作中の報告
            print(f"Thread ID: {self.id} is running.")
            # タイムアウトフラグ
            timeout_flag = False

            # aggregatorへの問い合わせ
            if firstCycleFlg:
                now = datetime.datetime.now()
                obj['status']['aggregated']['startedAt'] = now.strftime(
                    '%Y/%m/%d %H:%M:%S')

            # 現在のstatusをCRDに反映
            obj = change_status(
                self.group,
                self.namespace,
                self.version,
                self.plural,
                self.name,
                obj,
                self.api)
            if self.ns == "all":
                query = "?kind=" + self.kind
            else:
                query = "?ns=" + self.ns + "&kind=" + self.kind
            url = self.kubeAggregatorURL + "/api/v1/resource" + query
            # aggregatorからデータを取得する
            try:
                res = requests.get(url=url, verify=False, timeout=3.0)
            except Timeout:
                print(f"Thread ID: {self.id} aggregator request timed out.")
                timeout_flag = True
                pass

            # Update日時の設定
            now = datetime.datetime.now()
            obj['status']['aggregated']['updateAt'] = now.strftime(
                '%Y/%m/%d %H:%M:%S')
            # リクエスト結果
            if timeout_flag:
                obj['status']['aggregated']['success'] = "false"
                obj['status']['aggregated']['error'] = "Timeout"
                obj['status']['friendlyDescription'] = \
                    "Reconcile Failed : aggregated"
                obj = change_status(
                    self.group,
                    self.namespace,
                    self.version,
                    self.plural,
                    self.name,
                    obj,
                    self.api)
                time.sleep(self.minutes * 60)  # CRD の pollingTime 分待つ
                continue
            elif res.status_code == 200:
                obj['status']['aggregated']['success'] = "true"
                # 現在のstatusをCRDに反映
                obj = change_status(
                    self.group,
                    self.namespace,
                    self.version,
                    self.plural,
                    self.name,
                    obj,
                    self.api)
            else:
                obj['status']['aggregated']['success'] = "false"
                obj['status']['aggregated']['error'] = "status code is " + \
                    str(res.status_code)
                obj['status']['friendlyDescription'] = \
                    "Reconcile Failed : aggregated"
                # 現在のstatusをCRDに反映
                obj = change_status(
                    self.group,
                    self.namespace,
                    self.version,
                    self.plural,
                    self.name,
                    obj,
                    self.api)
                time.sleep(self.minutes * 60)  # CRD の pollingTime 分待つ
                continue

            # formatter問い合わせ
            if firstCycleFlg:
                now = datetime.datetime.now()
                obj['status']['formatted']['startedAt'] = now.strftime(
                    '%Y/%m/%d %H:%M:%S')
                firstCycleFlg = False

            # 現在のstatusをCRDに反映
            obj = change_status(
                self.group,
                self.namespace,
                self.version,
                self.plural,
                self.name,
                obj,
                self.api)
            # POST情報の設定
            url = self.kubeFormatterURL + "/api/v1/resource"
            headers = {
                'content-type': 'application/json'
            }
            json_data = res.text
            param = {
                'id': self.id
            }
            # formatter POST
            try:
                res = requests.post(
                    url=url,
                    headers=headers,
                    data=json_data,
                    verify=False,
                    params=param,
                    timeout=(
                        3.0,
                        300.0))
            except Timeout:
                timeout_flag = True
                pass

            # Update日時の設定
            now = datetime.datetime.now()
            obj['status']['formatted']['updateAt'] = now.strftime(
                '%Y/%m/%d %H:%M:%S')
            # リクエスト結果
            if timeout_flag:
                obj['status']['formatted']['success'] = "false"
                obj['status']['formatted']['error'] = "Timeout"
                obj['status']['friendlyDescription'] = \
                    "Reconcile Failed : formatted"
            elif res.status_code == 200:
                obj['status']['formatted']['success'] = "true"
                obj['status']['friendlyDescription'] = "Reconcile Succeeded"
            else:
                obj['status']['formatted']['success'] = "false"
                obj['status']['formatted']['error'] = "status code is " + \
                    str(res.status_code)
                obj['status']['friendlyDescription'] = \
                    "Reconcile Failed : formatted"
            # 現在のstatusをCRDに反映
            obj = change_status(
                self.group,
                self.namespace,
                self.version,
                self.plural,
                self.name,
                obj,
                self.api)

            # スレッドを一定時間停止（ポーリング間隔に基づく）
            print(f"Thread ID: {self.id} is sleeping for {self.minutes}m.")
            time.sleep(self.minutes * 60)  # CRD の pollingTime 分待つ

        # スレッドの終了を報告
        print(f"Thread ID: {self.id} has finished. ")


def read_crd():
    """
    Kubernetesのカスタムリソースを読み込み、スレッドを生成・管理する関数。
    """
    # Kubernetes上で動いているかを環境変数から判断
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        # ServiceAccountの権限で実行
        config.load_incluster_config()
    else:
        # $HOME/.kube/config から設定を読み込む
        config.load_kube_config()

    # カスタムオブジェクトAPIを生成
    api = client.CustomObjectsApi()

    # カスタムリソースの設定
    group = "sbp.vmware.jp"
    namespace = "default"
    version = "v1alpha1"
    plural = "spreadsheet"

    # カスタムリソースの変更を監視
    stream = watch.Watch().stream(
        api.list_namespaced_custom_object,
        group=group,
        namespace=namespace,
        version=version,
        plural=plural)

    threads = {}

    for event in stream:
        # イベントごとにスレッドを制御
        obj = event['object']
        operation = event['type']
        spec = obj.get('spec')

        if spec:
            name = obj['metadata']['name']

            if operation == "ADDED":
                minutes = format_pollingtime(spec['pollingTime'])
                # スレッドを動的に生成
                thread = StoppableThread(
                    namespace + name,
                    spec['kubeAggregatorURL'],
                    spec['kubeFormatterURL'],
                    spec['targetNamespace'],
                    spec['scrapeResource'],
                    minutes,
                    group,
                    namespace,
                    version,
                    plural,
                    name,
                    obj,
                    api)
                # スレッドを辞書型に追加
                threads[namespace + name] = thread
                # スレッドを開始
                thread.start()

            elif operation == "DELETED":
                # 特定のスレッドを停止
                threads[namespace + name].stop()


def change_status(group, namespace, version, plural, name, obj, api):
    """
    カスタムリソースのstatusフィールドを更新する関数。
    """
    retry_count = 5

    for _ in range(retry_count):
        try:
            # CRDのstatusフィールドを更新
            api.patch_namespaced_custom_object_status(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name,
                body=obj
            )
            # 更新後のオブジェクトを取得
            obj = api.get_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name,
            )
            break
        except client.exceptions.ApiException as e:
            if e.status == 409:  # 競合発生
                print("Conflict occurred when updating status, retrying...")
                # 競合解消のため、最新のオブジェクトを取得
                obj = api.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural,
                    name=name,
                )
            else:
                raise  # 競合以外のエラーは再スロー
    return obj


def format_pollingtime(pollingtime):
    """
    ポーリング時間をフォーマットする関数。
    """
    # 正規表現で時間(h)と分(m)を抽出
    h = re.search(r"(\d+)(?=h)", pollingtime)
    m = re.search(r"(\d+)(?=m)", pollingtime)

    # 時間を分に変換
    minutes = int(h.group()) * 60 if h else 0
    # 分を加算
    minutes += int(m.group()) if m else 0

    return minutes


if __name__ == "__main__":
    """
    メインの処理。Kubernetesのカスタムリソースを読み込み、それに基づいてスレッドを生成・管理する。
    """
    read_crd()
