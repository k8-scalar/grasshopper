package system

# Entry point to the policy. This is queried by the Kubernetes apiserver.
main = {
    "apiVersion": "admission.k8s.io/v1",
    "kind": "AdmissionReview",
    "response": response,
}

# If no other responses are defined, allow the request.


default uid := ""

uid := input.request.uid



response = {
    "allowed": true,
    "patchType": "JSONPatch",
    "uid": uid,
    "patch": base64url.encode(json.marshal(patches)),
} {
    patches := [p | p := patch[_][_]] # iterate over all patches and generate a flattened array
    count(patches) > 0
}

patch[[
    {
        "op": "add",
        "path": "/spec/nodeSelector",
        "value": {"segment": "good"},
    }
]] {


    # Only apply mutations to objects in create/update operations (not
    # delete/connect operations.)
    is_create_or_update

    # If the resource has the "test-mutation" annotation key, the patch will be
    # generated and applied to the resource.
    #input.request.object.metadata.namespace["test-mutation"]
}

is_create_or_update { is_create }
is_create_or_update { is_update }
is_create { input.request.operation == "CREATE" }
is_update { input.request.operation == "UPDATE" }
