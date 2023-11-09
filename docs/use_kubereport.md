# 使い方
## Kubernetes のリソース情報を minio 上の Excel に定期出力する
1. spreadsheet-sample.yamlを元にspreadsheet.yamlを作成し、取得したいリソースの種類やnamespace、取得間隔を指定する
    ```
    $ cd dev/
    $ cp ./spreadsheet-sample.yaml ./spreadsheet.yaml
    $ vim spreadsheet.yaml
    ```

1. spreadsheetの各keyの説明:  
    | Key | Value | Required | Notes |  
    | :--- | :--- | :--- | :--- |
    | kubeAggregatorURL | str | yes | aggregatorのservice URLを指定(devディレクトリの各種サンプルserviceを利用する場合は編集不要) |
    | kubeFormatterURL | str | yes | formatterのservice URLを指定(devディレクトリの各種サンプルserviceを利用する場合は編集不要) |
    | scrapeResource | str | yes | 取得したいリソースの種類を記載(README.mdの「取得可能な情報一覧」を参照) |
    | targetNamespace | str | no | 取得したいnamespaceを記載。記載しない場合、全てのnamespaceから取得する。また、StorageClassなどのnamespaceが存在しないクラスタスコープリソースに対してはtargetNamespaceを指定してはならない |
    | pollingTime | str | yes | リソース情報の取得間隔を時(h)、分(m)で指定。例えば、1時間30分間隔であれば、1h30mのように記載。

1. spreadsheet.yamlのサンプル
    ```
    apiVersion: sbp.vmware.jp/v1alpha1
    kind: Spreadsheet
    metadata:
        name: spreadsheet-sample
    spec:
        kubeAggregatorURL: http://aggregator:8080
        kubeFormatterURL: http://formatter:8080
        scrapeResource: Pod
        targetNamespace: default
        pollingTime: 2m
    ```

1. spreadsheet.yamlの適用
    ```
    $ kubectl apply -f spreadsheet.yaml
    ```

## minio 上の エクセルを回収する
1. 以下のコマンドで minio の Service を表示
    ```
    $ kubectl get svc
    ```
1. 1.のEXTERNAL-IPに表示されたIPアドレスへブラウザアクセスし、以下のログイン情報を使用  
    ID: minioadmin  
    Password: VMware1!  

1. Object Browserより「xlsx-upload-test」を選択

1. kubereport によりアップロードされたエクセルを選択し、Downloadを押下
