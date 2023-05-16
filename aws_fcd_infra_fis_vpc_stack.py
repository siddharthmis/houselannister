from aws_cdk import aws_ec2 as ec2
from aws_cdk.aws_ec2 import IVpc
from aws_cdk import core as cdk

class FisStackVpc(cdk.Stack):
    def __init__(self, scope: cdk.App, id: str, props=None):
        super().__init__(scope, id, props=props)
        self.vpc = ec2.Vpc(self, 'FisVpc',
            ip_addresses=ec2.IpAddress(cidr='10.0.0.0/16'),
            max_azs=2,
            subnet_configuration=[
                {
                    'cidr_mask': 24,
                    'name': "FisPub",
                    'subnet_type': ec2.SubnetType.PUBLIC
                },
                {
                    'cidr_mask': 24,
                    'name': "FisPriv",
                    'subnet_type': ec2.SubnetType.PRIVATE_WITH_EGRESS
                },
                {
                    'cidr_mask': 24,
                    'name': "FisIso",
                    'subnet_type': ec2.SubnetType.PRIVATE_ISOLATED
                },
            ]
        )
        cdk.CfnOutput(self, 'FisVpcId', value=self.vpc.vpc_id)
        for index, subnet in enumerate(self.vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnets):
            cdk.CfnOutput(self, 'FisPub' + str(index + 1), value=subnet.subnet_id)
        for index, subnet in enumerate(self.vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnets):
            cdk.CfnOutput(self, 'FisPriv' + str(index + 1), value=subnet.subnet_id)
        for index, subnet in enumerate(self.vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED).subnets):
            cdk.CfnOutput(self, 'FisIso' + str(index + 1), value=subnet.subnet_id)
