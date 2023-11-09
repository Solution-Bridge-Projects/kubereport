# リソースの追加方法
1. 利用したいリソースのKIND、APIVERSION、NAMEの確認  
  `kubectl api-resources` コマンドにて、取得したいリソースのKIND、APIVERSION、NAMEを確認  
    - 例:  
      Ingressであれば、  
      KIND: Ingress  
      APIVERSION: networking.k8s.io/v1  
      NAME: ingresses  

2. [kubereport/aggregator/aggregator/main.py](../aggregator/aggregator/main.py) のget_api_version_and_resource_type()内、mappingを編集
    APIグループが名前付きAPIグループか否かによって「`api/`」か「`apis/`」かが異なる
    - 例:  
      - Pod, Service, nodesなどのcoreに属するAPIVERSIONが`v1`となっているリソースの場合  
        ```
        "Pod": ("api/v1", "pods")
        ```
      - それ以外のcoreに属さないAPIVERSIONが`networking.k8s.io/v1`などの場合  
        Ingressであれば、mappingに以下を追記
        ```
        "Ingress": ("apis/networking.k8s.io/v1", "ingresses")
        ```

3. kubereport を [build](./build_kpack.md)
