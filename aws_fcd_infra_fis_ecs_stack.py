from aws_cdk import (
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    core as cdk
)

class EcsStack(cdk.Stack):
    def __init__(self, scope: cdk.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, 'FisVpc', vpc_name='FisStackVpc/FisVpc')
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        asg = autoscaling.AutoScalingGroup(self, "EcsAsgProvider",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.medium"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
            desired_capacity=1
        )

        cluster.add_capacity("CapacityProvider",
            auto_scaling_group=asg,
            capacity_provider_name="fisWorkshopCapacityProvider",
            enable_managed_termination_protection=False
        )

        # Add SSM access policy to nodegroup
        asg.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))

        task_definition = ecs.Ec2TaskDefinition(self, "SampleAppTaskDefinition")

        task_definition.add_container("SampleAppContainer",
            image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"),
            memory_limit_mib=256,
            port_mappings=[
                ecs.PortMapping(container_port=80, host_port=80)
            ]
        )

        sample_app_service = ecs_patterns.ApplicationLoadBalancedEc2Service(self, "SampleAppService",
            cluster=cluster,
            cpu=256,
            desired_count=1,
            memory_limit_mib=512,
            task_definition=task_definition
        )

        asg.attach_to_application_target_group(sample_app_service.target_group)

        ecs_url = cdk.CfnOutput(self, 'FisEcsUrl', value='http://' + sample_app_service.load_balancer.load_balancer_dns_name)
