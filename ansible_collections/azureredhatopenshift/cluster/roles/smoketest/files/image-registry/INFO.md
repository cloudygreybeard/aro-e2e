# Smoke Test: Internal Image Registry Validation

This component provides a two-stage smoke test to validate the integrity of the internal OpenShift image registry before and after cluster upgrades:

1. **Pushes a known public or local image to the internal registry**
   - Uses local standard `openshift/cli` image to avoid calls to public registries, necessary for example when testing disconnected clusters.
   - Uses `curl` to transfer the image into the cluster-local image registry.
   - Extracts and persists the image digest into a shared ConfigMap (`smoke-test-image-digest`).

2. **Verifies the pushed image via debug pod execution**  
   - Waits for the ConfigMap to be populated with the digest.
   - Launches a `oc debug` pod using the image from the registry by digest reference.
   - Confirms successful launch by checking for expected binary `/hello` within the container.

This provides a means by which image persistence can be tested, and ensures the registry’s write and read paths function as expected, thereby testing for upgrade-safe registry availability and data integrity.

---

### Implementation Notes:

- The test runs as two `Job` resources: `push-image` and `verify-image`.
- A `ConfigMap` acts as a durable handoff point between jobs.
- RBAC permissions are scoped tightly using a dedicated `ServiceAccount` and associated roles.
- The `push-image` supports both public and private/local image references. The image source is configurable via environment variables.

---

### Usage and Integration:

This component is expected to be used in conjunction with Ansible-based e2e test automation that runs pre-upgrade and post-upgrade validation.

To include this test in your pipeline:

1. Run the `push-image` as a pre-upgrade step.
2. Run the `verify-image` as a pre- and post-upgrade step. Logs should identify successful completion:
   ```
   $  oc logs -n smoke-test-image-registry -l job-name=verify-image -c verify
   ...Image verified successfully...
   ```


This model ensures the image is written *before* upgrade and verified *after*, providing a direct assertion of registry continuity across disruptive operations.

---

### Static render for resources pending inclusion of kustomize

Pending the inclusion of kustomize in the ansible image and jumphost definitions for aro-e2e, kustomization resources have been rendered to static resources as follows, to be applied by simple kubernetes.core.k8s module actions:

```shell
$ for overlay_path in overlays/*; do \
    overlay=$(basename "${overlay_path}"); \
    kustomize build "${overlay_path}" > ./statics/resources.${overlay}.yaml; \
  done
```
