# Kubereport

## 概要
Kubernetes のリソース情報を収集し Excel に定期出力します。  
出力された Excel は minio から GUI アクセスにより、ダウンロードできます。

## 取得可能な情報一覧
- kind
  - Pod
  - Service
  - Deployment
  - ReplicaSet
  - StatefulSet
  - StorageClass
  - Spreadsheet (CRD用サンプル)
- 他のリソースを取得したい場合、[リソースの追加方法](./docs/add_resource.md)を参照 (要build)

## コンポーネント
[![Architecture](/docs/image/architecture.png)]()  
  
- **aggregator**
  - Kubernetes クラスタから API でリソース情報を取得する。
- **controller**
  - 作成された CRD の状態を維持管理して aggregator と formatter に命令を定期的に送る。
    - CRD で指定したリソース情報を取得するように aggregator に命令を送る。
    - aggregator で取得したリソース情報を formatter に送る。
- **formatter**
  - aggregator が取得したリソース情報を Excel フォーマットに整形し、minio にアップロードする。
- **minio**
  - OSS の S3 互換オブジェクトストレージ。ファイルサーバとして利用。GUI が提供されるので、それを操作して Excel をダウンロードする。

## システム要件
- Kubernetes クラスタ
- 4core vCPU, 8GB MEM(1nodeで全コンポーネントを動作させる場合)

## 各種手順
1. [(開発者向け)ソースコードをコンテナイメージへbuildする](./docs/build_kpack.md)
    - 利用するだけであれば [dockerhub](https://hub.docker.com/repositories/sbpimage) にコンテナイメージがあるため、この手順は不要
1. [コンテナイメージをkubernetes環境へ展開する](./docs/install_kubereport.md)
1. [kubernetesのリソース情報をminio上のエクセルへ出力する](./docs/use_kubereport.md)


## ロードマップ
- 複数k8sクラスタを任意に選択する
- 専用 GUI の実装
- Helm チャート対応

## 関連リンク集
- [dockerhub](https://hub.docker.com/repositories/sbpimage)
- X(twitter) [Solution Bridge Projects](https://twitter.com/SolutionBridgeP)
