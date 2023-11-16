# kubereportのインストール方法
## 前提条件
- kubereportを動作させるkubernetes実行環境....(1)
  - Service(Loadbalancer)が必要
- kubereportにて情報取得予定のkubernetesクラスタ環境....(2)
- 作業端末に`kubectl`コマンド、`ytt`コマンドがインストール済み
  - 以下ドキュメントを参考にyttコマンドをinstall
      - Carvelツール群  
        https://docs.vmware.com/en/VMware-Tanzu-Kubernetes-Grid/1.6/vmware-tanzu-kubernetes-grid-16/GUID-install-cli.html#install-the-carvel-tools-7  

## インストール手順
1. 事前準備: kubereport実行用aggregator configmapを作成
    - ディレクトリの移動
        ```
        cd dev/aggregator/
        ```
        - 以下、コンテキストは`kubectl config use-context xxxx`にて(2)に設定
    - serviceacconut(SA)の作成
        ```
        kubectl apply -f aggregator_serviceaccount.yaml
        ```
    - SAとclusterroleの紐付け(clusterrolebinding)
        ```
        kubectl apply -f aggregator_clusterrolebinding.yaml
        ```
    - トークンの作成
        ```
        kubectl create token aggregator-serviceaccount -n default --duration=4294967296s
        ```
        - トークン作成のサンプル
            ```
            $ kubectl create token aggregator-serviceaccount -n default --duration=4294967296s
            eyJhbGciOiJSUzI1NiIsImtpZCI6IjQ0WkZUSmVjYW8wOWl4RGRpLV9IZ2Y4UXZaSmVtVUtJRHlJUENrMTVKdTQifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiXSwiZXhwIjo1OTgzMDAxNjQ0LCJpYXQiOjE2ODgwMzQzNDgsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJkZWZhdWx0Iiwic2VydmljZWFjY291bnQiOnsibmFtZSI6ImRlZmF1bHQiLCJ1aWQiOiI2NjI0YzlkNy0yNzFiLTRmNjctYWQ2Yy1mODY4NzEyNTAzNTkifX0sIm5iZiI6MTY4ODAzNDM0OCwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6ZGVmYXVsdCJ9.Xk-Kvtd7F43rNR1lkoVaiWGxUcDOuudHjO4RbGB64zcikRD9BbO7h9ifQXWvDodFjKuLRoUyWhxlCBNLIrAievNwrvGNaA9mF_c1DIsz747D7cMjeL8WR5phptyBQN71LMwVZZLEoidL3FzHCOoJy4_Dg80FxfN_YXyp2NwngMDYKEVhe3a2BfYc5TWfqTsYJ6mZd7eO1Wap4pWPTI49EsNwsJ20qDD5BdCN9wWMz2Ht_505EBFCV5r3MpexpBT54M_dSvYLPoeJL-wyzSxh-yWBv2XFQcTBp9gqDnEWOilbwU6i470KHgnRtC2PYbrLN2e6-xA_DYV2bjgoj7KOHA
            ```
    - 出力結果をコピーしてconfigmapを作成  
    例: aggregator_configmap.yaml
        ```
        apiVersion: v1
        data:
          ip: <kubernetes cluster API endpoint IP address or FQDN>:<port>
          token: eyJhbGciOiJSUzI1NiIsImtpZCI6IjQ0WkZUSmVjYW8wOWl4RGRpLV9IZ2Y4UXZaSmVtVUtJRHlJUENrMTVKdTQifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiXSwiZXhwIjo1OTgzMDAxNjQ0LCJpYXQiOjE2ODgwMzQzNDgsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJkZWZhdWx0Iiwic2VydmljZWFjY291bnQiOnsibmFtZSI6ImRlZmF1bHQiLCJ1aWQiOiI2NjI0YzlkNy0yNzFiLTRmNjctYWQ2Yy1mODY4NzEyNTAzNTkifX0sIm5iZiI6MTY4ODAzNDM0OCwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6ZGVmYXVsdCJ9.Xk-Kvtd7F43rNR1lkoVaiWGxUcDOuudHjO4RbGB64zcikRD9BbO7h9ifQXWvDodFjKuLRoUyWhxlCBNLIrAievNwrvGNaA9mF_c1DIsz747D7cMjeL8WR5phptyBQN71LMwVZZLEoidL3FzHCOoJy4_Dg80FxfN_YXyp2NwngMDYKEVhe3a2BfYc5TWfqTsYJ6mZd7eO1Wap4pWPTI49EsNwsJ20qDD5BdCN9wWMz2Ht_505EBFCV5r3MpexpBT54M_dSvYLPoeJL-wyzSxh-yWBv2XFQcTBp9gqDnEWOilbwU6i470KHgnRtC2PYbrLN2e6-xA_DYV2bjgoj7KOHA
        kind: ConfigMap
        metadata:
          name: aggregator-config
        ```
    - configmapの展開
        - 以下、コンテキストは`kubectl config use-context xxxx`にて(1)に設定
        ```
        kubectl apply -f aggregator_configmap.yaml
        ```

1. イメージの展開 (kubereportのインストール)
    - kubereportの各構成要素をコンテナとして起動
        - controller
            ```
            cd dev/controller/k8s/ytt
            ```
            ```
            ytt -f ../ --data-value-yaml namespace=default --data-value-yaml image=sbpimage/kubereport-controller | kubectl apply -f-
            ```

        - aggregator
            ```
            cd dev/aggregator/
            ```
            ```
            kubectl apply -f aggregator_deployment.yaml
            kubectl apply -f aggregator_svc.yaml
            ```

        - formatter
            ```
            cd dev/formatter/
            ```
            ```
            kubectl apply -f formatter_deployment.yaml
            kubectl apply -f formatter_svc.yaml
            ```

    - エクセル格納先のS3バケット互換ストレージの用意
        - minio
            ```
            cd dev/minio/
            ```
            ```
            kubectl apply -f minio.yaml
            ```
