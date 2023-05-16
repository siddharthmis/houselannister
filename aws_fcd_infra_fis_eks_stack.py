import aws_cdk as cdk
from constructs import Construct
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_eks as eks
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_logs as logs

class EksStack(cdk.Stack):
    counter: int
    def __init__(self, scope: Construct, id: str, props=None) -> None:
        super().__init__(scope, id, props=props)
        vpc = ec2.Vpc.from_lookup(self, 'FisVpc', vpc_name='FisStackVpc/FisVpc')
        eksCluster = eks.Cluster(self, 'Cluster', 
            vpc=vpc,
            version=eks.KubernetesVersion.V1_24,
            default_capacity=0,
            cluster_name="FisWorkshop-EksCluster"
        )
        lt = ec2.CfnLaunchTemplate(self, 'LaunchTemplate', 
            launch_template_data={
                'instanceType': 't3.medium',
                'tagSpecifications': [{
                    'resourceType': 'instance',
                    'tags': [{
                        'key': 'Name',
                        'value': 'FisEKSNode',
                    }],
                }]
            }
        )
        eksNodeGroup = eksCluster.add_nodegroup_capacity("ManagedNodeGroup", 
            desired_size=1,
            nodegroup_name="FisWorkshopNG",
            tags={
                "Name": "FISTarget"
            },
            launch_template_spec={
                'id': lt.ref,
                'version': lt.attr_latest_version_number,
            }
        )

        eksNodeGroup.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
app_label = { "app": "hello-kubernetes" }
deployment = {
  "apiVersion": "apps/v1",
  "kind": "Deployment",
  "metadata": { "name": "hello-kubernetes" },
  "spec": {
    "replicas": 1,
    "selector": { "matchLabels": app_label },
    "template": {
      "metadata": { "labels": app_label },
      "spec": {
        "containers": [
          {
            "name": "hello-kubernetes",
            "image": "paulbouwer/hello-kubernetes:1.5",
            "ports": [ { "containerPort": 8080 } ]
          }
        ]
      }
    }
  }
}
service = {
  "apiVersion": "v1",
  "kind": "Service",
  "metadata": { "name": "hello-kubernetes" },
  "spec": {
    "type": "LoadBalancer",
    "ports": [ { "port": 80, "targetPort": 8080 } ],
    "selector": app_label
  }
}
eks_cluster.add_manifest('hello-kub', service, deployment)
eks_url = core.CfnOutput(self, 'FisEksUrl', value='http://' + eks_cluster.get_service_load_balancer_address("hello-kubernetes"))
kube_ctl_role = core.CfnOutput(self, 'FisEksKubectlRole', value=eks_cluster.kubectl_role.role_arn if eks_cluster.kubectl_role else "")
counter = 1
for construct in self.node.find_all():
    if isinstance(construct, aws_lambda.Function):
        logs.LogGroup(self, f"LogGroup{counter}", 
                      log_group_name=f"/aws/lambda/{construct.function_name}",
                      retention=logs.RetentionDays.THREE_MONTHS,
                      removal_policy=core.RemovalPolicy.DESTROY)
        counter += 1
