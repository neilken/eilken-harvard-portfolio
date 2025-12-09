import os
import pulumi
import pulumi_docker_build as docker_build
from pulumi_gcp import artifactregistry
from pulumi import CustomTimeouts
import datetime

# 🔧 Get project info
project = pulumi.Config("gcp").require("project")
location = os.environ["GCP_REGION"]

# 🕒 Timestamp for tagging
timestamp_tag = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
repository_name = "stockbusters-app-repository"
registry_url = f"us-central1-docker.pkg.dev/{project}/{repository_name}"

# Docker Build + Push -> API Service
image_config = {
    "image_name": "stockbusters-app-api-service",
    "context_path": "../../api-service",
    "dockerfile": "Dockerfile"
}
api_service_image = docker_build.Image(
    f"build-{image_config["image_name"]}",
    tags=[pulumi.Output.concat(registry_url, "/", image_config["image_name"], ":", timestamp_tag)],
    context=docker_build.BuildContextArgs(location=image_config["context_path"]),
    dockerfile={"location": f"{image_config["context_path"]}/{image_config["dockerfile"]}"},
    platforms=[docker_build.Platform.LINUX_AMD64],
    push=True,
    opts=pulumi.ResourceOptions(custom_timeouts=CustomTimeouts(create="30m"),
                                retain_on_delete=True)
)
# Export references to stack
pulumi.export("stockbusters-app-api-service-ref", api_service_image.ref)
pulumi.export("stockbusters-app-api-service-tags", api_service_image.tags)

# Docker Build + Push -> Frontend
image_config = {
    "image_name": "stockbusters-app-frontend",
    "context_path": "../../frontend",
    "dockerfile": "Dockerfile"
}
frontend_image = docker_build.Image(
    f"build-{image_config["image_name"]}",
    tags=[pulumi.Output.concat(registry_url, "/", image_config["image_name"], ":", timestamp_tag)],
    context=docker_build.BuildContextArgs(location=image_config["context_path"]),
    dockerfile={"location": f"{image_config["context_path"]}/{image_config["dockerfile"]}"},
    platforms=[docker_build.Platform.LINUX_AMD64],
    push=True,
    opts=pulumi.ResourceOptions(custom_timeouts=CustomTimeouts(create="30m"),
                                retain_on_delete=True)
)
pulumi.export("stockbusters-app-frontend-ref", frontend_image.ref)
pulumi.export("stockbusters-app-frontend-tags", frontend_image.tags)

#Docker Build + Push -> vector-db-cli
# image_config = {
    # "image_name": "stockbusters-app-vector-db-cli",
    # "context_path": "../../vector-db",
    # "dockerfile": "Dockerfile"
# }
# frontend_image = docker_build.Image(
    # f"build-{image_config["image_name"]}",
    # tags=[pulumi.Output.concat(registry_url, "/", image_config["image_name"], ":", timestamp_tag)],
    # context=docker_build.BuildContextArgs(location=image_config["context_path"]),
    # dockerfile={"location": f"{image_config["context_path"]}/{image_config["dockerfile"]}"},
    # platforms=[docker_build.Platform.LINUX_AMD64],
    # push=True,
    # opts=pulumi.ResourceOptions(custom_timeouts=CustomTimeouts(create="30m"),
                                # retain_on_delete=True)
# )
#Export references to stack
# pulumi.export("stockbusters-app-vector-db-cli-ref", frontend_image.ref) #need to correct the ref
# pulumi.export("stockbusters-app-vector-db-cli-tags", frontend_image.tags) #need to correct the tag