"""Known vendor services: how to recognise them, how locked-in they are, how to port them.

lockin: 1 = open standard / drop-in elsewhere, 2 = compatible API or moderate rewrite,
3 = proprietary, needs a redesign.
data: category used for egress sizing (storage, database, other) or None when no bulk data lives there.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Service:
    key: str
    provider: str
    name: str
    category: str
    lockin: int
    data: str | None
    alternatives: str
    steps: tuple = field(default_factory=tuple)


def _s(key, provider, name, category, lockin, data, alternatives, *steps):
    return Service(key, provider, name, category, lockin, data, alternatives, tuple(steps))


DATA_CATEGORIES = ("storage", "database")

SERVICES = {s.key: s for s in [
    _s("aws_s3", "aws", "Amazon S3", "storage", 2, "storage", "Hetzner/Scaleway/OVH/Exoscale Object Storage, MinIO, Garage",
       "List buckets, sizes, versioning and lifecycle rules; decide whether old versions move too",
       "Copy with rclone or `aws s3 sync` to the S3-compatible target, then verify object counts and checksums",
       "Replace bucket policies/IAM roles and presigned-URL code (endpoint, region, path-style addressing)"),
    _s("aws_ebs", "aws", "Amazon EBS / EFS", "storage", 2, "storage", "Block volume or NFS on the target provider",
       "Snapshot, then copy as raw image or rsync file contents; schedule a final delta sync during cut-over"),
    _s("aws_rds", "aws", "Amazon RDS / Aurora", "database", 2, "database", "Self-managed or managed PostgreSQL/MySQL (Scaleway, OVH, Hetzner VM)",
       "Check engine and extensions (Aurora-specific features do not move)",
       "Dump (pg_dump/mysqldump) or set up logical replication to the target; rehearse a restore and time it",
       "Plan the write freeze window and DNS/connection-string switch"),
    _s("aws_dynamodb", "aws", "Amazon DynamoDB", "database", 3, "database", "ScyllaDB (Alternator), PostgreSQL JSONB, MongoDB",
       "Export table to S3/JSON; redesign access patterns, there is no drop-in API elsewhere",
       "Rewrite every SDK call and secondary-index query"),
    _s("aws_lambda", "aws", "AWS Lambda", "serverless", 3, None, "OpenFaaS, Knative, containers behind a small HTTP server",
       "Inventory triggers (API Gateway, S3, SQS, schedules); each trigger needs a replacement",
       "Wrap handlers into a container or framework and rebuild the event wiring"),
    _s("aws_apigw", "aws", "API Gateway", "network", 3, None, "Traefik, Kong, nginx",
       "Export OpenAPI definitions; rebuild auth, throttling and stages in the new gateway"),
    _s("aws_sqs_sns", "aws", "SQS / SNS / EventBridge", "queue", 3, None, "RabbitMQ, NATS, Redis streams, PostgreSQL queues",
       "Drain queues before cut-over; map topics/subscriptions and dead-letter queues to the new broker"),
    _s("aws_ecs_eks", "aws", "ECS / EKS / Fargate", "compute", 2, None, "Kubernetes (k3s/managed), Docker Compose, Nomad",
       "EKS manifests and Helm charts port well; replace IAM-for-service-accounts, ALB ingress and EBS CSI classes",
       "ECS task definitions must be rewritten as compose/Kubernetes manifests"),
    _s("aws_ec2", "aws", "Amazon EC2", "compute", 1, None, "Any VPS or bare-metal provider",
       "Capture the configuration as code (cloud-init/Ansible); AMIs do not move, rebuild images"),
    _s("aws_elb_cdn", "aws", "ELB / CloudFront / Route 53", "network", 2, None, "Caddy/nginx/HAProxy, Bunny CDN, any DNS host",
       "Lower DNS TTLs a week before; export Route 53 zone files; recreate TLS certificates (ACM certs are not exportable)"),
    _s("aws_iam_cognito", "aws", "IAM / Cognito / Secrets Manager", "identity", 3, None, "Keycloak, Authentik, Vault, SOPS",
       "Export user pools (password hashes are NOT exportable from Cognito: plan a reset or lazy migration)",
       "Move secrets to the new store and rotate every one of them"),
    _s("aws_cloudwatch", "aws", "CloudWatch / X-Ray", "monitoring", 2, None, "Prometheus + Grafana + Loki, OpenTelemetry",
       "Re-create dashboards and alarms; keep an archive of logs your compliance rules require"),
    _s("aws_cache", "aws", "ElastiCache", "database", 1, None, "Redis/Valkey/Memcached anywhere", "Cache can usually be rebuilt cold; check persistence and eviction settings"),
    _s("aws_ml", "aws", "SageMaker / Bedrock / Textract / Rekognition", "ml", 3, None, "Self-hosted models, other EU AI APIs",
       "Export trained artefacts and datasets; managed AI APIs have no like-for-like replacement"),
    _s("aws_other", "aws", "Other AWS services", "other", 2, None, "Review one by one"),
    _s("az_blob", "azure", "Azure Blob / Files / Disks", "storage", 2, "storage", "S3-compatible object storage, MinIO, rclone targets",
       "Copy with azcopy or rclone; check access tiers (cool/archive blobs need rehydration first)",
       "Replace SAS-token and managed-identity access code"),
    _s("az_sql", "azure", "Azure SQL / PostgreSQL / MySQL", "database", 2, "database", "Self-managed or managed PostgreSQL/MySQL in the EU",
       "Azure SQL (T-SQL) ports to SQL Server elsewhere or needs a rewrite; PostgreSQL/MySQL flexible servers dump and restore normally",
       "Rehearse restore, then plan a write freeze for the final sync"),
    _s("az_cosmos", "azure", "Cosmos DB", "database", 3, "database", "MongoDB, PostgreSQL JSONB, Cassandra", "Export with Data Factory or the migration tool; the API mode (Mongo/Cassandra/SQL) decides how hard the move is"),
    _s("az_functions", "azure", "Azure Functions / Logic Apps", "serverless", 3, None, "OpenFaaS, Knative, containers", "Inventory triggers and bindings; rebuild each trigger on the target"),
    _s("az_servicebus", "azure", "Service Bus / Event Hubs / Event Grid", "queue", 3, None, "RabbitMQ, NATS, Kafka", "Drain queues first; map topics and dead-letter queues"),
    _s("az_aks_vm", "azure", "AKS / VMs / App Service / Container Apps", "compute", 2, None, "Kubernetes or Docker Compose on any provider",
       "AKS manifests port; replace Azure-specific ingress, disks and workload identity", "App Service needs repackaging as containers"),
    _s("az_network", "azure", "Front Door / App Gateway / DNS", "network", 2, None, "Caddy/nginx/HAProxy, any DNS host", "Export DNS zones and WAF rules; recreate certificates"),
    _s("az_identity", "azure", "Entra ID / Key Vault", "identity", 3, None, "Keycloak, Authentik, Vault, SOPS", "Plan identity federation or a user migration; rotate all Key Vault secrets"),
    _s("az_monitor", "azure", "Azure Monitor / App Insights", "monitoring", 2, None, "OpenTelemetry + Grafana stack", "Re-create dashboards and alerts; export retained logs"),
    _s("az_redis", "azure", "Azure Cache for Redis", "database", 1, None, "Redis/Valkey anywhere", "Cache can be rebuilt cold"),
    _s("az_ml", "azure", "Azure OpenAI / Cognitive / ML", "ml", 3, None, "Self-hosted models, other EU AI APIs", "Export datasets and fine-tuned artefacts where licences allow"),
    _s("az_other", "azure", "Other Azure services", "other", 2, None, "Review one by one"),
    _s("gcp_gcs", "gcp", "Cloud Storage (GCS)", "storage", 2, "storage", "S3-compatible object storage, MinIO", "Copy with rclone/`gcloud storage cp`; replace signed URLs and IAM conditions"),
    _s("gcp_disk", "gcp", "Persistent Disk / Filestore", "storage", 2, "storage", "Block or NFS storage on the target", "Snapshot and copy as image or rsync; schedule a final delta"),
    _s("gcp_sql", "gcp", "Cloud SQL / AlloyDB / Spanner", "database", 2, "database", "Managed PostgreSQL/MySQL in the EU",
       "Cloud SQL dumps normally; Spanner and AlloyDB-specific features have no equivalent and need a redesign"),
    _s("gcp_bigquery", "gcp", "BigQuery / Bigtable / Firestore", "database", 3, "database", "ClickHouse, PostgreSQL, DuckDB, MongoDB",
       "Export to Parquet/Avro on GCS (export itself is free, the egress of the files is not); rewrite SQL dialect and pipelines"),
    _s("gcp_functions", "gcp", "Cloud Functions / Cloud Run", "serverless", 2, None, "Containers anywhere (Cloud Run is container-based, so it ports well)",
       "Cloud Run: move the image and env; Cloud Functions: wrap in a container with the Functions Framework"),
    _s("gcp_pubsub", "gcp", "Pub/Sub / Tasks / Scheduler", "queue", 3, None, "RabbitMQ, NATS, Kafka", "Drain subscriptions first; map topics to the new broker"),
    _s("gcp_gke_vm", "gcp", "GKE / Compute Engine", "compute", 2, None, "Kubernetes or VMs elsewhere", "GKE manifests port; replace GCE disks, load balancers and Workload Identity"),
    _s("gcp_network", "gcp", "Cloud DNS / Load Balancing / CDN", "network", 2, None, "Caddy/nginx/HAProxy, any DNS host", "Export DNS zones; recreate certificates and LB rules"),
    _s("gcp_identity", "gcp", "IAM / Identity Platform / Secret Manager / Firebase Auth", "identity", 3, None, "Keycloak, Authentik, Vault, SOPS",
       "Firebase Auth exports users, but hash parameters must be kept; rotate every secret"),
    _s("gcp_monitor", "gcp", "Cloud Logging / Monitoring", "monitoring", 2, None, "OpenTelemetry + Grafana stack", "Re-create dashboards and alerts; export retained logs"),
    _s("gcp_redis", "gcp", "Memorystore", "database", 1, None, "Redis/Valkey anywhere", "Cache can be rebuilt cold"),
    _s("gcp_ml", "gcp", "Vertex AI / Vision / Speech", "ml", 3, None, "Self-hosted models, other EU AI APIs", "Export datasets and trained artefacts"),
    _s("gcp_other", "gcp", "Other Google Cloud services", "other", 2, None, "Review one by one"),
]}

# (provider, regex on the Terraform resource type or the SDK/name token) -> service key; first match wins.
TERRAFORM_RULES = [
    ("aws", r"^aws_(s3|glacier)", "aws_s3"),
    ("aws", r"^aws_(ebs_|efs_|fsx_|volume_attachment)", "aws_ebs"),
    ("aws", r"^aws_(db_|rds_)", "aws_rds"),
    ("aws", r"^aws_dynamodb", "aws_dynamodb"),
    ("aws", r"^aws_(lambda_|serverlessapplicationrepository)", "aws_lambda"),
    ("aws", r"^aws_(api_gateway|apigatewayv2)", "aws_apigw"),
    ("aws", r"^aws_(sqs_|sns_|cloudwatch_event|scheduler_|sfn_|pipes_)", "aws_sqs_sns"),
    ("aws", r"^aws_(ecs_|eks_|ecr_|batch_|apprunner)", "aws_ecs_eks"),
    ("aws", r"^aws_(instance|launch_|autoscaling_|ami|key_pair|spot_)", "aws_ec2"),
    ("aws", r"^aws_(lb|alb|elb|cloudfront_|route53_|acm_|wafv2_|globalaccelerator)", "aws_elb_cdn"),
    ("aws", r"^aws_(iam_|cognito_|secretsmanager_|kms_|ssm_)", "aws_iam_cognito"),
    ("aws", r"^aws_(cloudwatch_(log|metric|dashboard)|xray_)", "aws_cloudwatch"),
    ("aws", r"^aws_elasticache", "aws_cache"),
    ("aws", r"^aws_(sagemaker_|bedrock|textract|rekognition|comprehend)", "aws_ml"),
    ("aws", r"^aws_(vpc|subnet|security_group|internet_gateway|nat_gateway|route_table|eip|network_)", None),
    ("aws", r"^aws_", "aws_other"),
    ("azure", r"^azurerm_(storage_|managed_disk)", "az_blob"),
    ("azure", r"^azurerm_(mssql_|sql_|postgresql_|mysql_|mariadb_)", "az_sql"),
    ("azure", r"^azurerm_cosmosdb", "az_cosmos"),
    ("azure", r"^azurerm_(function_app|linux_function_app|windows_function_app|logic_app)", "az_functions"),
    ("azure", r"^azurerm_(servicebus_|eventhub|eventgrid_)", "az_servicebus"),
    ("azure", r"^azurerm_(kubernetes_|linux_virtual_machine|windows_virtual_machine|virtual_machine|service_plan|linux_web_app|windows_web_app|container_app|container_registry)", "az_aks_vm"),
    ("azure", r"^azurerm_(frontdoor|cdn_|application_gateway|dns_|private_dns_|lb)", "az_network"),
    ("azure", r"^azurerm_(key_vault|user_assigned_identity|role_|disk_encryption_set)", "az_identity"),
    ("azure", r"^azurerm_(monitor_|application_insights|log_analytics)", "az_monitor"),
    ("azure", r"^azurerm_redis", "az_redis"),
    ("azure", r"^azurerm_(cognitive_|machine_learning_)", "az_ml"),
    ("azure", r"^azurerm_(resource_group|virtual_network|subnet|network_|public_ip)", None),
    ("azure", r"^azurerm_", "az_other"),
    ("gcp", r"^google_(storage_|filestore_)", "gcp_gcs"),
    ("gcp", r"^google_compute_(disk|snapshot|image)", "gcp_disk"),
    ("gcp", r"^google_(sql_|alloydb_|spanner_)", "gcp_sql"),
    ("gcp", r"^google_(bigquery_|bigtable_|firestore_|datastore_)", "gcp_bigquery"),
    ("gcp", r"^google_(cloudfunctions|cloud_run|cloudfunctions2)", "gcp_functions"),
    ("gcp", r"^google_(pubsub_|cloud_tasks_|cloud_scheduler_)", "gcp_pubsub"),
    ("gcp", r"^google_(container_|compute_instance|compute_region_instance|artifact_registry)", "gcp_gke_vm"),
    ("gcp", r"^google_(dns_|compute_(backend|url_map|forwarding|global_forwarding|target_|ssl))", "gcp_network"),
    ("gcp", r"^google_(project_iam|service_account|secret_manager|identity_platform|kms_|iam_)", "gcp_identity"),
    ("gcp", r"^google_(logging_|monitoring_)", "gcp_monitor"),
    ("gcp", r"^google_redis", "gcp_redis"),
    ("gcp", r"^google_(vertex_ai|ml_engine|document_ai)", "gcp_ml"),
    ("gcp", r"^google_(compute_network|compute_subnetwork|compute_firewall|compute_address|project$|project_service)", None),
    ("gcp", r"^google_", "gcp_other"),
]

# SDK packages and image names are weaker evidence than infrastructure code; they map to the same keys.
SDK_RULES = [
    (r"^(boto3|botocore|aioboto3|s3fs|aws-cdk-lib|aws-lambda-powertools)$", "aws", "aws_other"),
    (r"^(@aws-sdk/client-s3|@aws-sdk/lib-storage|aws-sdk)$", "aws", "aws_s3"),
    (r"^@aws-sdk/client-dynamodb|^@aws-sdk/lib-dynamodb", "aws", "aws_dynamodb"),
    (r"^@aws-sdk/client-(sqs|sns|eventbridge)", "aws", "aws_sqs_sns"),
    (r"^@aws-sdk/", "aws", "aws_other"),
    (r"^(azure-storage-blob|@azure/storage-blob)$", "azure", "az_blob"),
    (r"^(azure-cosmos|@azure/cosmos)$", "azure", "az_cosmos"),
    (r"^(azure-servicebus|@azure/service-bus|azure-eventhub|@azure/event-hubs)$", "azure", "az_servicebus"),
    (r"^(azure-identity|@azure/identity|azure-keyvault.*|@azure/keyvault.*)$", "azure", "az_identity"),
    (r"^(azure-functions|@azure/functions)$", "azure", "az_functions"),
    (r"^(azure-|@azure/)", "azure", "az_other"),
    (r"^(google-cloud-storage|@google-cloud/storage)$", "gcp", "gcp_gcs"),
    (r"^(google-cloud-bigquery|@google-cloud/bigquery|google-cloud-bigtable|google-cloud-firestore|@google-cloud/firestore|firebase-admin|firebase)$", "gcp", "gcp_bigquery"),
    (r"^(google-cloud-pubsub|@google-cloud/pubsub)$", "gcp", "gcp_pubsub"),
    (r"^(google-cloud-|@google-cloud/|google-api-python-client|googleapis)", "gcp", "gcp_other"),
]

IMAGE_RULES = [
    (r"(^|/)(public\.ecr\.aws|[0-9]+\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com)(/|$)", "aws", "aws_ecs_eks"),
    (r"^(amazon/aws-cli|amazon/dynamodb-local|localstack/localstack|amazon/aws-lambda-)", "aws", "aws_other"),
    (r"^(mcr\.microsoft\.com/azure-|mcr\.microsoft.com/azure-storage/azurite)", "azure", "az_blob"),
    (r"^mcr\.microsoft\.com/(mssql|azure-sql-edge)", "azure", "az_sql"),
    (r"^(gcr\.io|[a-z0-9-]+-docker\.pkg\.dev|eu\.gcr\.io|us\.gcr\.io)/", "gcp", "gcp_gke_vm"),
    (r"^(google/cloud-sdk|gcr\.io/google\.com/cloudsdktool)", "gcp", "gcp_other"),
]

# Host fragments found in connection strings and endpoint values.
ENDPOINT_RULES = [
    (r"\.rds\.amazonaws\.com|\.rds\.[a-z0-9-]+\.amazonaws\.com", "aws", "aws_rds"),
    (r"s3[.-][a-z0-9-]*\.?amazonaws\.com|\.s3\.amazonaws\.com", "aws", "aws_s3"),
    (r"dynamodb\.[a-z0-9-]+\.amazonaws\.com", "aws", "aws_dynamodb"),
    (r"\.cache\.amazonaws\.com", "aws", "aws_cache"),
    (r"sqs\.[a-z0-9-]+\.amazonaws\.com|sns\.[a-z0-9-]+\.amazonaws\.com", "aws", "aws_sqs_sns"),
    (r"\.blob\.core\.windows\.net", "azure", "az_blob"),
    (r"\.database\.windows\.net|\.postgres\.database\.azure\.com|\.mysql\.database\.azure\.com", "azure", "az_sql"),
    (r"\.documents\.azure\.com", "azure", "az_cosmos"),
    (r"\.servicebus\.windows\.net", "azure", "az_servicebus"),
    (r"\.redis\.cache\.windows\.net", "azure", "az_redis"),
    (r"storage\.googleapis\.com", "gcp", "gcp_gcs"),
    (r"firestore\.googleapis\.com|bigquery\.googleapis\.com", "gcp", "gcp_bigquery"),
    (r"pubsub\.googleapis\.com", "gcp", "gcp_pubsub"),
    (r"\.cloudsql|/cloudsql/", "gcp", "gcp_sql"),
]

# Environment variable names that prove a provider is used even when the value is empty or a placeholder.
ENV_KEY_RULES = [
    (r"^AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY|SESSION_TOKEN|DEFAULT_REGION|REGION|PROFILE)$", "aws", "aws_other"),
    (r"^(S3_BUCKET|AWS_S3_BUCKET|S3_BUCKET_NAME)$", "aws", "aws_s3"),
    (r"^(AZURE_STORAGE_[A-Z_]+)$", "azure", "az_blob"),
    (r"^AZURE_(CLIENT_ID|CLIENT_SECRET|TENANT_ID|SUBSCRIPTION_ID)$", "azure", "az_identity"),
    (r"^(GOOGLE_APPLICATION_CREDENTIALS|GCP_PROJECT|GOOGLE_CLOUD_PROJECT|GCLOUD_PROJECT)$", "gcp", "gcp_other"),
    (r"^(FIREBASE_[A-Z_]+|GCS_BUCKET)$", "gcp", "gcp_bigquery"),
]

# Terraform attributes that make an exit more expensive and deserve a warning of their own.
RISK_PATTERNS = [
    (r"\b(GLACIER|DEEP_ARCHIVE|GLACIER_IR)\b", "Archive storage class found: restoring takes hours/days and carries retrieval fees on top of egress, and early-deletion minimums may apply."),
    (r"\b(reserved_instance|savings_plan|reservation)\b", "Reserved/committed capacity found: remaining commitment is usually owed even after you leave. It is not a Data Act switching charge."),
    (r"\bmulti_az\b\s*=\s*true", "Multi-AZ/HA databases: the target needs a comparable replica setup or the cut-over loses redundancy."),
    (r"\bkms_key_id\b|\bkms_key_name\b|\bkms_master_key_id\b", "Provider-managed KMS keys: data encrypted with them is only readable after decrypting inside the provider. Export plaintext (or re-encrypt) before closing the account."),
]

# CloudFormation "AWS::<Namespace>::" and Bicep/ARM "Microsoft.<Namespace>/" prefixes. None = plain networking.
CFN_NAMESPACES = {
    "S3": "aws_s3", "Glacier": "aws_s3", "EFS": "aws_ebs", "FSx": "aws_ebs", "RDS": "aws_rds", "DynamoDB": "aws_dynamodb",
    "Lambda": "aws_lambda", "ApiGateway": "aws_apigw", "ApiGatewayV2": "aws_apigw", "SQS": "aws_sqs_sns", "SNS": "aws_sqs_sns",
    "Events": "aws_sqs_sns", "StepFunctions": "aws_sqs_sns", "ECS": "aws_ecs_eks", "EKS": "aws_ecs_eks", "ECR": "aws_ecs_eks",
    "EC2": None, "AutoScaling": "aws_ec2", "ElasticLoadBalancingV2": "aws_elb_cdn", "ElasticLoadBalancing": "aws_elb_cdn",
    "CloudFront": "aws_elb_cdn", "Route53": "aws_elb_cdn", "CertificateManager": "aws_elb_cdn", "WAFv2": "aws_elb_cdn",
    "IAM": "aws_iam_cognito", "Cognito": "aws_iam_cognito", "SecretsManager": "aws_iam_cognito", "KMS": "aws_iam_cognito",
    "SSM": "aws_iam_cognito", "Logs": "aws_cloudwatch", "CloudWatch": "aws_cloudwatch", "ElastiCache": "aws_cache",
    "SageMaker": "aws_ml", "Bedrock": "aws_ml",
}
BICEP_NAMESPACES = {
    "Storage": "az_blob", "Sql": "az_sql", "DBforPostgreSQL": "az_sql", "DBforMySQL": "az_sql", "DocumentDB": "az_cosmos",
    "ServiceBus": "az_servicebus", "EventHub": "az_servicebus", "EventGrid": "az_servicebus", "ContainerService": "az_aks_vm",
    "Compute": "az_aks_vm", "Web": "az_aks_vm", "App": "az_aks_vm", "ContainerRegistry": "az_aks_vm", "Network": None,
    "Cdn": "az_network", "KeyVault": "az_identity", "ManagedIdentity": "az_identity", "Authorization": "az_identity",
    "Insights": "az_monitor", "OperationalInsights": "az_monitor", "Cache": "az_redis", "CognitiveServices": "az_ml",
    "MachineLearningServices": "az_ml",
}

# Single-line signals in YAML/JSON/Bicep files (Kubernetes manifests, Helm values, serverless.yml, CI files).
KEYWORD_RULES = [
    (r"\bebs\.csi\.aws\.com\b|kubernetes\.io/aws-ebs", "aws", "aws_ebs", "AWS EBS storage class"),
    (r"alb\.ingress\.kubernetes\.io|service\.beta\.kubernetes\.io/aws-load-balancer", "aws", "aws_elb_cdn", "AWS load-balancer annotation"),
    (r"eks\.amazonaws\.com/role-arn", "aws", "aws_iam_cognito", "IAM role for service account"),
    (r"disk\.csi\.azure\.com|kubernetes\.io/azure-disk|file\.csi\.azure\.com", "azure", "az_blob", "Azure disk/file storage class"),
    (r"azure\.workload\.identity/", "azure", "az_identity", "Azure workload identity"),
    (r"service\.beta\.kubernetes\.io/azure-", "azure", "az_network", "Azure load-balancer annotation"),
    (r"pd\.csi\.storage\.gke\.io|kubernetes\.io/gce-pd", "gcp", "gcp_disk", "GCE persistent disk class"),
    (r"iam\.gke\.io/gcp-service-account|cloud\.google\.com/[a-z-]+", "gcp", "gcp_gke_vm", "GKE annotation"),
]
