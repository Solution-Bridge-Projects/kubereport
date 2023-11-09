kubereport build方法

1. k8s環境を用意
1. 作業用端末にてdockerおよびkubectlをインストール
1. コンテキストを設定
    ```
    kubectl config use-context XXXX
    ```
    または  
    ```
    export KUBECONFIG=XXX.yml
    ```

1. buildツールインストール
    - kp  
        kpackの最新リリースダウンロード  
        ```        
        KP="$(curl -w "%{redirect_url}" -s -o /dev/null https://github.com/buildpacks-community/kpack/releases/latest | awk -F "/tag/" '{print $2}')"  
        wget https://github.com/buildpacks-community/kpack/releases/download/$KP/release-${KP:1}.yaml
        ```
        ダウンロードしたrelease-0.xx.x.yamlをビルド  
        ```
        kubectl apply -f release-0.12.2.yaml
        ```
        dockerレジストリ用のsecret作成  
        ```
        kubectl create secret docker-registry dockerhub-secret --docker-username=<dockerhub username> --docker-password=<password> --docker-server=https://index.docker.io/v1/ 
        ```  
        docker image pull用のsecret作成(上記とは別に必要)  
        ```
        kubectl create secret docker-registry dockerhub-secret-image-pull --docker-username=<dockerhub username> --docker-password=<password> --docker-server=index.docker.io 
        ```  
        kpack-components.yamlを作成する    
        ```
        ---
        apiVersion: v1
        kind: ServiceAccount
        metadata:
          name: dockerhub-sa
        secrets:
        - name: dockerhub-secret
        imagePullSecrets:
        - name: dockerhub-secret-image-pull
        ---
        apiVersion: kpack.io/v1alpha2
        kind: ClusterStore
        metadata:
          name: kubereport-store
        spec:
          sources:
          - image: gcr.io/paketo-buildpacks/builder:base
        ---
        apiVersion: kpack.io/v1alpha2
        kind: ClusterStack
        metadata:
          name: kubereport-full
        spec:
          id: "io.buildpacks.stacks.bionic"
          buildImage:
            image: "paketobuildpacks/build:base-cnb"
          runImage:
            image: "paketobuildpacks/run:base-cnb"
        ---
        apiVersion: kpack.io/v1alpha2
        kind: Builder
        metadata:
          name: kubereport-builder
        spec:
          serviceAccountName: dockerhub-sa
          tag: <dockerhub username>/kubereport-builder      # 要変更
          stack:
            name: kubereport-full
            kind: ClusterStack
          store:
            name: kubereport-store
            kind: ClusterStore
          order:
          - group:
            - id: paketo-buildpacks/poetry-run
          - group:
            - id: paketo-buildpacks/poetry
          - group:
            - id: paketo-buildpacks/java
          - group:
            - id: paketo-buildpacks/nodejs
          - group:
            - id: paketo-buildpacks/python
          - group:
            - id: paketo-buildpacks/python-start
          - group:
            - id: paketo-buildpacks/procfile
        ```
        SA, CludStore, ClusterStack, Builderをまとめてビルド    
        ```
        kubectl apply -f kpack-components.yaml
        ```
        少し待ってからBuilderがReadyになってることが確認できたらimage作成ができる  
        ```
        kubectl get Builder
        NAME      LATESTIMAGE                                                                                           
            READY
        default   sys12-harbor.vmtss.com/sbp/builder@sha256:951807ad7c456c3d8cc4df95f1ba8f8b4f75b62c1d2c477376802fa2e8063385   True
        ```
    - 以下ドキュメントを参考にkpコマンドをinstall
      - Carvelツール群  
        https://docs.vmware.com/en/VMware-Tanzu-Kubernetes-Grid/1.6/vmware-tanzu-kubernetes-grid-16/GUID-install-cli.html#install-the-carvel-tools-7  

1. コンテナリポジトリ用意  
    docker-hubを使う

1. イメージ作成 (build)
    - codeをcloneして移動する
        ```
        git clone https://github.com/Solution-Bridge-Projects/kubereport.git
        cd kubereport
        ```
    - dockerhubにログイン  
        前提: docker engineが起動している事  
        ```
        docker login 
        Username: <dockerhubのユーザ>
        Password: <dockerhubのパスワード>
        Login Succeeded
        ```
    - それぞれのコンポーネントをbuildする。
        - controller
            ```
            cd kubereport
            cd controller/controller
            kp image save kubereport-controller --local-path ./ --tag <your dockerhub user name>/kubereport-controller --wait -b kubereport-builder --service-account dockerhub-sa
            ```

        - aggregator  
            ```
            cd kubereport
            cd aggregator/aggregator/
            kp image save kubereport-aggregator --local-path ./  --tag <your dockerhub user name>/kubereport-aggregator --wait -b kubereport-builder --service-account dockerhub-sa
            ```

        - formatter  
            ```
            cd kubereport
            cd formatter/formatter/
            kp image save kubereport-formatter --local-path ./  --tag <your dockerhub user name>/kubereport-formatter --wait -b kubereport-builder --service-account dockerhub-sa
            ```

