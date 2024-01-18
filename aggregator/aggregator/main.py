from loguru import logger
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import os
import sys
import requests
from requests.exceptions import Timeout
import datetime

# stdout, stderr, stdinのバッファリングを設定
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)
sys.stdin = os.fdopen(sys.stdin.fileno(), 'r', buffering=1)

app = FastAPI()


def get_api_version_and_resource_type(kind):
    """
    KubernetesのKindからAPIバージョンとリソースタイプのURL情報を取得

    Parameters:
    - kind: Kubernetesのリソースの種類

    Returns:
    - api_version: APIバージョンのURL情報
    - resource_type: リソースタイプのURL情報

    Raises:
    - ValueError: サポートされていないリソースの場合
    """
    # aggregatorが対応しているkindの種類を定義
    # 対応させたいリソースタイプを増やす場合は以下に同様にリソースを追記すれば良い
    mapping = {
        "Pod": ("api/v1", "pods"),
        "Service": ("api/v1", "services"),
        "Deployment": ("apis/apps/v1", "deployments"),
        "ReplicaSet": ("apis/apps/v1", "replicasets"),
        "StatefulSet": ("apis/apps/v1", "statefulsets"),
        "Spreadsheet": ("apis/sbp.vmware.jp/v1alpha1", "spreadsheet"),
        "StorageClass": ("apis/storage.k8s.io/v1", "storageclasses")
    }
    # mapping情報をもとにkindからapi_version, resource_typeを検索
    api_version, resource_type = mapping.get(kind, (None, None))

    # api_versionとresource_typeが存在していればそれを返す、存在していなければエラーを返す
    if api_version and resource_type:
        return api_version, resource_type

    raise ValueError("kind: " + kind + " is not supported")


@app.get("/api/v1/resource", response_class=JSONResponse)
def get_kubernetes_resource(ns: str = None, kind: str = None):
    """
    Kubernetesクラスタから指定されたリソースのjson情報を取得し、fastapiをコールしたクライアントに情報を返す

    Parameters:
    - ns: 対象となるnamespace。指定しない場合は全てのnamespace。
    - kind: 取得するリソースの種類。

    Returns:
    - res_body: リソースのjson情報
    """
    # aggregatorの処理開始時刻をログに記録
    now = datetime.datetime.now()
    logger.info("get_kubernetes_resource START! " +
          now.strftime('%Y年%m月%d日%H:%M:%S'))

    # configmapから生成されたファイルより、k8sクラスタのトークンを取得
    path = '/tmp/k8sClusterToken'
    with open(path) as f:
        token = f.read().strip()

    # configmapから生成されたファイルより、k8sクラスタのIPアドレスを取得
    path = '/tmp/k8sClusterIPaddress'
    with open(path) as f:
        k8sClusterIPaddress = f.read().strip()

    # 取得したIPアドレスを元にベースURLを生成
    base_url = "https://" + k8sClusterIPaddress + "/"

    # APIのエンドポイントURLを生成
    try:
        api_version, resource_type = get_api_version_and_resource_type(kind)
    except ValueError as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="internal error")

    # namespaceの指定がない場合、すべてのnsを対象とする
    if ns is None:
        url = base_url + api_version + "/" + resource_type
    else:
        url = base_url + api_version + "/namespaces/" + ns + \
            "/" + resource_type

    # リクエストヘッダを定義してAPIエンドポイントへリクエスト送信
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/json"}
    try:
        res = requests.get(url=url, headers=headers, verify=False, timeout=3.0)
    except Timeout:
        raise HTTPException(status_code=408, detail="Timeout")

    # レスポンスからリソースのjsonデータを取得
    res_body = res.text

    # aggregatorの処理終了時刻をログに記録
    now = datetime.datetime.now()
    logger.info("get_kubernetes_resource DONE! " + now.strftime('%Y年%m月%d日%H:%M:%S'))

    # リソースのjson情報をreturn
    return res_body

if __name__ == "__main__":
    # アプリケーションの起動設定
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
