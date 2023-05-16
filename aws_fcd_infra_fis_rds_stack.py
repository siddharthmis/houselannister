from aws_cdk import (
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager,
    core as cdk,
)
from aws_cdk.aws_ec2 import InstanceType


class FisStackRdsAurora(cdk.Stack):
    def __init__(self, scope: cdk.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        vpc = ec2.Vpc.from_lookup(self, "FisVpc", vpc_name="FisStackVpc/FisVpc")
        rds_security_group = ec2.SecurityGroup(
            self,
            "rdsSecurityGroup",
            vpc=vpc,
            security_group_name="FisRdsSecurityGroup",
            description="Allow mysql access to RDS",
            allow_all_outbound=True,
        )  # Can be set to false
        rds_security_group.add_ingress_rule(
            peer=rds_security_group,
            connection=ec2.Port.tcp(3306),
            description="allow mysql access from self",
        )
        aurora_credentials = rds.Credentials.from_generated_secret(
            "clusteradmin", secret_name="FisAuroraSecret"
        )

        aurora = rds.DatabaseCluster(
            self,
            "FisWorkshopRdsAurora",
            engine=rds.DatabaseClusterEngine.aurora_mysql(
                version=rds.AuroraMysqlEngineVersion.VER_2_11_1
            ),
            credentials=auroraCredentials,
            default_database_name="testdb",
            instance_props={
                "vpc_subnets": {"subnet_type": ec2.SubnetType.PRIVATE_WITH_EGRESS},
                "vpc": vpc,
                "security_groups": [rdsSecurityGroup],
            },
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        mysqlCredentials = rds.Credentials.from_generated_secret(
            "clusteradmin", secret_name="FisMysqlSecret"
        )

        mysql = rds.DatabaseInstance(
            self,
            "FisWorkshopRdsMySql",
            vpc=vpc,
            vpc_subnets={"subnet_type": ec2.SubnetType.PRIVATE_WITH_EGRESS},
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_5_7
            ),
            credentials=mysqlCredentials,
            database_name="testdb",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            multi_az=True,
            security_groups=[rdsSecurityGroup],
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Store things in SSM so we can coordinate multiple stacks


rds_security_group_param = ssm.StringParameter(
    scope=self,
    id="FisWorkshopRdsSgId",
    parameter_name="FisWorkshopRdsSgId",
    string_value=rds_security_group.security_group_id,
)
rds_aurora_secret_arn = ssm.StringParameter(
    scope=self,
    id="FisWorkshopAuroraSecretArn",
    parameter_name="FisWorkshopAuroraSecretArn",
    string_value=aurora.secret.secret_full_arn if aurora.secret else "UNDEFINED",
)
rds_mysql_secret_arn = ssm.StringParameter(
    scope=self,
    id="FisWorkshopMysqlSecretArn",
    parameter_name="FisWorkshopMysqlSecretArn",
    string_value=mysql.secret.secret_full_arn if mysql.secret else "UNDEFINED",
)

# Expose values to workshop users
aurora_host_name = cdk.CfnOutput(
    scope=self, id="FisAuroraHostName", value=aurora.cluster_endpoint.hostname
)
mysql_host_name = cdk.CfnOutput(
    scope=self, id="FisMysqlHostName", value=mysql.db_instance_endpoint_address
)
aurora_secret = cdk.CfnOutput(
    scope=self,
    id="FisAuroraSecret",
    value=aurora.secret.secret_full_arn if aurora.secret else "UNDEFINED",
)
mysql_secret = cdk.CfnOutput(
    scope=self,
    id="FisMysqlSecret",
    value=mysql.secret.secret_full_arn if mysql.secret else "UNDEFINED",
)
