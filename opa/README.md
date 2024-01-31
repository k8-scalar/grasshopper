##  
(based on [OPA Kubernetes Tutorial](https://www.openpolicyagent.org/docs/latest/kubernetes-tutorial/) and [Torin Sandall's Mutating Admission Webhook example](https://gist.github.com/tsandall/f328635433acc5beeb4cb9b36295ee89))

This tutorial assumes the OPA policy store is running on the master node. We assume that the master node does not allow scheduling of Pods that do not tolerate the NoSchedule taint.
Moreeover, the master node of your K8s cluster should have the following node label: `node-role.kubernetes.io/control-plane: ""`

First ensure this opa directory is copied to your master node and cd into it.
 
Then execute the following commands on the master node:

### Create a new Namespace to deploy OPA into

```
kubectl create namespace opa
```

### Create TLS credentials for OPA

Communication between Kubernetes and OPA must be secured using TLS. To configure TLS, use openssl to create a certificate authority (CA) and certificate/key pair for OPA:

```
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -sha256 -key ca.key -days 100000 -out ca.crt -subj "/CN=admission_ca"
```

Generate the TLS key and certificate for OPA:

```
cat >server.conf <<EOF
[ req ]
prompt = no
req_extensions = v3_ext
distinguished_name = dn

[ dn ]
CN = opa.opa.svc

[ v3_ext ]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth, serverAuth
subjectAltName = DNS:opa.opa.svc,DNS:opa.opa.svc.cluster,DNS:opa.opa.svc.cluster.local
EOF
```

```
openssl genrsa -out server.key 2048
openssl req -new -key server.key -sha256 -out server.csr -extensions v3_ext -config server.conf
openssl x509 -req -in server.csr -sha256 -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 100000 -extensions v3_ext -extfile server.conf
```

***Note: the Common Name value and Subject Alternative Name you give to openssl MUST match the name of the OPA service created below.***

Create a Secret to store the TLS credentials for OPA:

```
kubectl create secret tls opa-server --cert=server.crt --key=server.key --namespace opa
```

### Install the policy store

```
./deploy-policy-store.sh
```

### If policies are not yet build by OPA
The following command assumes the docker engine is installed

```
cd policies
docker run --user root -v $PWD:/examples openpolicyagent/opa build -b /examples -o /examples/bundle.tar.gz
cd ..
```


### Install OPA's admission webhook server

```
kubectl apply -f ac.yaml -n opa
```

When OPA starts, the kube-mgmt container will load Kubernetes namespaces and policies objects into OPA. 
You can configure the sidecar to load any kind of Kubernetes object into OPA. 
The sidecar establishes watches on the Kubernetes API server so that OPA has access 
to an eventually consistent cache of Kubernetes objects.

Next, generate the manifest that will be used to register OPA as an admission controller. This webhook will ignore any namespace with the label openpolicyagent.org/webhook=ignore.


### Register webhook with K8s control plane

Next, generate the manifest that will be used to register OPA as an admission controller. This webhook will ignore any namespace with the label openpolicyagent.org/webhook=ignore.

```
cat > webhook-configuration.yaml <<EOF
kind: ValidatingWebhookConfiguration
apiVersion: admissionregistration.k8s.io/v1
metadata:
  name: opa-validating-webhook
webhooks:
  - name: validating-webhook.openpolicyagent.org
    namespaceSelector:
      matchExpressions:
      - key: openpolicyagent.org/webhook
        operator: NotIn
        values:
        - ignore
    rules:
      - operations: ["CREATE", "UPDATE"]
        apiGroups: ["*"]
        apiVersions: ["*"]
        resources: ["*"]
    clientConfig:
      caBundle: $(cat ca.crt | base64 | tr -d '\n')
      service:
        namespace: opa
        name: opa
    admissionReviewVersions: ["v1"]
    sideEffects: None
EOF
```

The generated configuration file includes a base64 encoded representation of the CA certificate 
created above so that TLS connections can be established between the Kubernetes API server and OPA.

Next label kube-system and the opa namespace so that OPA does not control the resources in those namespaces.

```
kubectl label ns kube-system openpolicyagent.org/webhook=ignore
kubectl label ns opa openpolicyagent.org/webhook=ignore
```

Finally register the web hook with the K8s API server.

```
kubectl apply -f webhook-configuration.yaml
```

You can follow the OPA logs to see the webhook requests being issued by the Kubernetes API server:

```
# ctrl-c to exit
kubectl logs -l app=opa -c opa -f -n opa
```

### Remove OPA

```
kubectl delete -f webhook-configuration.yaml
kubectl delete -f ac.yaml -n opa
./delete-policy-store.sh
kubectl delete secret opa-server -n opa
rm *.key *.crt *.conf *.csr
```
