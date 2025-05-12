#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# github.com/cloudygreybeard, 2025

import os
import sys
import json
import re
import subprocess
import tempfile
import base64
import hashlib
import argparse
import logging

def parse_args():
    parser = argparse.ArgumentParser(description="Push an OCI image tarball to an OpenShift image registry.")
    parser.add_argument("registry", nargs="?", help="Registry hostname")
    parser.add_argument("repository", nargs="?", help="Repository (project/image)")
    parser.add_argument("tarball", nargs="?", help="Path to OCI tarball")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging (redacted)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging (unredacted)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without uploading")
    return parser.parse_args()

def redact(text):
    return re.sub(r'(?i)(Bearer\s+)[a-zA-Z0-9._-]+', r'\1<REDACTED>', text)

def log(msg, config):
    if config.get("debug"):
        logging.debug(msg)
    elif config.get("verbose"):
        logging.info(redact(msg))

def setup_logging(debug):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=level)

def get_config():
    args = parse_args()
    registry = args.registry or os.environ.get("REGISTRY")
    repository = args.repository or (
        f"{os.environ.get('PROJECT')}/{os.environ.get('IMAGE_NAME')}"
        if os.environ.get("PROJECT") and os.environ.get("IMAGE_NAME")
        else None
    )
    tarball = args.tarball or os.environ.get("TARBALL")

    if not all([registry, repository, tarball]):
        print("Missing config: registry, repository, and tarball required.")
        sys.exit(1)

    verbose = args.verbose or os.environ.get("VERBOSITY", "0") == "1"
    debug = args.debug or os.environ.get("DEBUG", "0") == "1"

    return {
        "registry": registry,
        "repository": repository,
        "tarball": tarball,
        "tag": os.environ.get("TAG", "latest"),
        "ca_cert": os.environ.get("CA_CERT", "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"),
        "token_path": os.environ.get("TOKEN_PATH", "/var/run/secrets/kubernetes.io/serviceaccount/token"),
        "verbose": verbose,
        "debug": debug,
        "dry_run": args.dry_run,
    }

def sha256_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"

def run_curl(method, url, data=None, headers=None, extra_args=None, input_file=None, ca_cert=None, token_path=None, config=None):
    token = open(token_path).read().strip()
    cmd = ["curl", "-sfL", "-X", method]
    if config.get("debug"):
        cmd.insert(1, "-v")

    cmd += [
        "--cacert", ca_cert,
        "-H", f"Authorization: Bearer {token}",
        *[item for h in (headers or []) for item in ("-H", h)],
    ]

    if data:
        cmd += ["--data-binary", "@-"]
    if input_file:
        cmd += ["--upload-file", input_file]
    if extra_args:
        cmd += extra_args

    cmd.append(url)

    with tempfile.NamedTemporaryFile() as header_file:
        cmd += ["-D", header_file.name]

        log("Running curl: " + ' '.join(cmd), config)

        result = subprocess.run(
            cmd,
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        headers = open(header_file.name).read()

    log("stdout:\n" + result.stdout.decode(), config)
    log("stderr:\n" + result.stderr.decode(), config)
    log("headers:\n" + redact(headers), config)

    if result.returncode != 0:
        raise RuntimeError(f"Curl failed: returncode={result.returncode}")
    return result, headers

def upload_blob(repo, blob_path, digest, config):
    log(f"Uploading blob {digest} ...", config)
    _, headers = run_curl(
        method="POST",
        url=f"https://{config['registry']}/v2/{repo}/blobs/uploads/",
        ca_cert=config["ca_cert"],
        token_path=config["token_path"],
        config=config
    )

    location = None
    for line in headers.splitlines():
        match = re.search(r'^Location:\s*(.+)$', line, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            break

    if not location:
        raise RuntimeError("Failed to extract Location header from response")

    put_url = f"{location}&digest={digest}" if "?" in location else f"{location}?digest={digest}"
    run_curl("PUT", put_url, input_file=blob_path, ca_cert=config["ca_cert"], token_path=config["token_path"], config=config)

def upload_manifest(repo, manifest, tag, config):
    manifest_json = json.dumps(manifest).encode()
    _, headers = run_curl(
        "PUT",
        f"https://{config['registry']}/v2/{repo}/manifests/{tag}",
        data=manifest_json,
        headers=["Content-Type: application/vnd.oci.image.manifest.v1+json"],
        ca_cert=config["ca_cert"],
        token_path=config["token_path"],
        config=config
    )

    digest = None
    for line in headers.splitlines():
        match = re.search(r'^Docker-Content-Digest:\s*([a-z0-9]+:[a-f0-9]+)$', line, re.IGNORECASE)
        if match:
            digest = match.group(1).strip()
            break

    if not digest:
        raise RuntimeError("Failed to extract Docker-Content-Digest from registry response")

    return digest

def create_configmap_with_digest(digest, config):
    """Create a ConfigMap with the image digest"""
    configmap_name = "smoke-test-image-digest"

    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            namespace = f.read().strip()
    except FileNotFoundError:
        print("Namespace file not found.")
        sys.exit(1)

    cmd = [
        "oc", "create", "configmap", configmap_name,
        "--from-literal=digest=" + digest,
        "-n", namespace
    ]
    
    log(f"Creating ConfigMap {configmap_name} in namespace {namespace} with digest.", config)
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create ConfigMap: {result.stderr.decode()}")
    log(f"ConfigMap {configmap_name} created successfully in namespace {namespace}.", config)

def main():
    config = get_config()
    setup_logging(config["debug"])
    repo = config["repository"]

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["tar", "-xf", config["tarball"], "-C", tmpdir], check=True)

        with open(os.path.join(tmpdir, "index.json")) as f:
            index = json.load(f)

        algo, hash_value = index["manifests"][0]["digest"].split(":")
        manifest_path = os.path.join(tmpdir, "blobs", algo, hash_value)
        with open(manifest_path) as f:
            manifest = json.load(f)

        blobs = [manifest["config"]] + manifest["layers"]
        for blob in blobs:
            algo, hash_value = blob["digest"].split(":")
            blob_path = os.path.join(tmpdir, "blobs", algo, hash_value)
            actual_digest = sha256_digest(blob_path)
            assert actual_digest == blob["digest"], f"Digest mismatch for {blob_path}"
            upload_blob(repo, blob_path, blob["digest"], config)

        manifest_digest = upload_manifest(repo, manifest, config["tag"], config)
        print("Upload complete.")

        create_configmap_with_digest(manifest_digest, config)

if __name__ == "__main__":
    main()
