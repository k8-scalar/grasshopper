curl -sSk   --header "Authorization: Bearer $(cat token.txt)" https://172.23.24.76:6443/api/v1/namespaces/cass-operator/pods/dummy-cass-operator |  jq -r '.metadata.uid'
