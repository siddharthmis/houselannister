from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as alb,
    aws_logs as log,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cwactions,
    aws_ssm as ssm,
    core
)
from aws_cdk.aws_ec2 import Protocol
from aws_cdk.aws_elasticloadbalancingv2 import ApplicationProtocol

class AsgCdkTestStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        # Set some constants for convenience
        fisLogGroup = '/fis-workshop/fis-logs'
        nginxAccessLogGroup = '/fis-workshop/asg-access-log'
        nginxErrorLogGroup = '/fis-workshop/asg-error-log'
        # Query existing resources - will this work if we pull this into an app?
        vpc = ec2.Vpc.from_lookup(self, 'FisVpc', vpc_name='FisStackVpc/FisVpc')

        rdsSgId = ssm.StringParameter.from_string_parameter_attributes(
    this, 'MyValue', parameter_name='FisWorkshopRdsSgId'
).string_value
rds_security_group = ec2.SecurityGroup.from_security_group_id(
    this, 'FisWorkshopRdsSg', rdsSgId
)
my_security_group = ec2.SecurityGroup(
    this, 'SecurityGroup', vpc=vpc, description='Allow HTTP access to ec2 instances', allow_all_outbound=True
)
my_security_group.add_ingress_rule(
    ec2.Peer.any_ipv4(), ec2.Port.tcp(80), 'allow http access from the world'
)
my_security_group.connections.allow_from(rds_security_group, ec2.Port.all_tcp())
rds_security_group.connections.allow_from(my_security_group, ec2.Port.all_tcp())
amazon2 = ec2.MachineImage.from_ssm_parameter(
    '/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-ebs', os=ec2.OperatingSystemType.LINUX
)
instance_role = iam.Role(
    this, 'FisInstanceRole', assumed_by=iam.ServicePrincipal('ec2.amazonaws.com'),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSSMManagedInstanceCore'),
        iam.ManagedPolicy.from_aws_managed_policy_name('CloudWatchAgentServerPolicy')
    ]
)
instance_role.add_to_principal_policy(iam.PolicyStatement(
    resources=['*'], actions=['secretsmanager:GetSecretValue', 'cloudformation:DescribeStacks'],
    effect=iam.Effect.ALLOW
))


import boto3
import os
import mustache
import fs

ec2 = boto3.resource('ec2')
autoscaling = boto3.client('autoscaling')

myASG = autoscaling.create_auto_scaling_group(
    AutoScalingGroupName='ASG',
    VPCZoneIdentifier=vpc,
    InstanceType='t2.micro',
    Role=instanceRole,
    ImageId=amazon2,
    MinSize=1,
    MaxSize=9,
    Metrics=[autoscaling.GroupMetrics.all()],
    DesiredCapacity=1,
    LaunchConfigurationName='my-launch-config'
)

user_data = mustache.render(fs.readFileSync('./assets/create_db.py', 'utf8'),{
    auroraSecretArn: 'FisAuroraSecret',
    mysqlSecretArn: 'FisMysqlSecret',
})

ec2.create_instances(
    ImageId=amazon2,
    InstanceType='t2.micro',
    MinCount=1,
    MaxCount=9,
    UserData=user_data,
    KeyName='my-key-pair'
)

user_data = mustache.render(fs.readFileSync('./assets/test_mysql_connector_curses.py', 'utf8'),{
    auroraSecretArn: 'FisAuroraSecret',
    mysqlSecretArn: 'FisMysqlSecret',
})

ec2.create_instances(
    ImageId=amazon2,
    InstanceType='t2.micro',
    MinCount=1,
    MaxCount=9,
    UserData=user_data,
    KeyName='my-key-pair'
)

import os
import boto3
from aws_cdk import (
    aws_autoscaling as autoscaling,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cwactions,
    core as cdk
)

userDataScript = open('./assets/user-data.sh', 'r').read()
myASG.add_user_data(userDataScript)
myAsgCpuMetric = cloudwatch.Metric(
    namespace='AWS/EC2',
    metric_name='CPUUtilization',
    dimensions={
        'AutoScalingGroupName': myASG.auto_scaling_group_name
    },
    period=cdk.Duration.minutes(1)
)
myAsgCpuAlarmHigh = cloudwatch.Alarm(
    scope=this,
    id='FisAsgHighCpuAlarm',
    metric=myAsgCpuMetric,
    threshold=90.0,
    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
    evaluation_periods=1,
    # datapoints_to_alarm=1,
)
myAsgCpuAlarmLow = cloudwatch.Alarm(
    scope=this,
    id='FisAsgLowCpuAlarm',
    metric=myAsgCpuMetric,
    threshold=20.0,
    comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_OR_EQUAL_TO_THRESHOLD,
    evaluation_periods=3,
    # datapoints_to_alarm=2,
)
myAsgManualScalingActionUp = autoscaling.StepScalingAction(
    scope=this,
    id='ScaleUp',
    auto_scaling_group=myASG,
    adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
    # cooldown=cdk.Duration.minutes(1)
)
myAsgManualScalingActionUp.add_adjustment(
    adjustment=1,
    lower_bound=0,
    # upper_bound=100
)
myAsgCpuAlarmHigh.add_alarm_action(cwactions.AutoScalingAction(auto_scaling_group=myAsgManualScalingActionUp))

myAsgManualScalingActionDown = autoscaling.StepScalingAction(
    self, "ScaleDown",
    auto_scaling_group=myASG,
    adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
    # cooldown=cdk.Duration.minutes(1)
)
myAsgManualScalingActionDown.add_adjustment(
    adjustment=-1,
    upper_bound=0,
    # lower_bound=-100
)
myAsgCpuAlarmLow.add_alarm_action(
    cwactions.AutoScalingAction(myAsgManualScalingActionDown)
)
lb = alb.ApplicationLoadBalancer(
    self, 'FisAsgLb',
    vpc=vpc,
    internet_facing=True
)
listener = lb.add_listener(
    'FisAsgListener',
    port=80
)
tg1 = alb.ApplicationTargetGroup(
    self, 'FisAsgTargetGroup',
    target_type=alb.TargetType.INSTANCE,
    port=80,
    targets=[myASG],
    vpc=vpc,
    health_check={
        'healthy_http_codes': '200-299',
        'healthy_threshold_count': 2,
        'interval': Duration(seconds=20),
        'timeout': Duration(seconds=15),
        'unhealthy_threshold_count': 10,
        'path': '/'
    }
)
listener.add_target_groups(
    'FisTargetGroup',
    target_groups=[tg1]
)
listener.connections.allow_default_port_from_any_ipv4('Open to the world')
lbUrl = cdk.CfnOutput(
    self, 'FisAsgUrl',
    value='http://' + lb.load_balancer_dns_name
)
# Getting AZs from LB because ASG construct doesn't seem to expose them
fisAzs = lb.vpc.availability_zones if lb.vpc else ['none', 'none']

outputFisAz1 = cdk.CfnOutput(self, 'FisAlbAz1', value=fisAzs[0])
outputFisAz2 = cdk.CfnOutput(self, 'FisAlbAz2', value=fisAzs[1])
logGroupFisLogs = log.LogGroup(self, 'FisLogGroupFisLogs', logGroupName=fisLogGroup, retention=log.RetentionDays.ONE_WEEK)
outputFisLog = cdk.CfnOutput(self, 'FisLogsArn', value=logGroupFisLogs.logGroupArn)
logGroupNginxAccess = log.LogGroup(self, 'FisLogGroupNginxAccess', logGroupName=nginxAccessLogGroup, retention=log.RetentionDays.ONE_WEEK)
for element in [2, 4, 5]:
    log.MetricFilter(self, 'NginxMetricsFilter' + str(element) + 'xx', logGroup=logGroupNginxAccess, metricNamespace='fisworkshop', metricName=str(element) + 'xx', filterPattern=log.FilterPattern.string_value('$.status','=',str(element) + '*'), metricValue='1', defaultValue=0)
log.MetricFilter(self, 'NginxMetricsFilterDuration', logGroup=logGroupNginxAccess, metricNamespace='fisworkshop', metricName='duration', filterPattern=log.FilterPattern.number_value('$.request_time','>=',0), metricValue='$.request_time', defaultValue=0)

log_group_nginx_error = log.LogGroup(
    self, 'FisLogGroupNginxError',
    log_group_name=nginx_error_log_group,
    retention=log.RetentionDays.ONE_WEEK
)

# Escape hatch does not replace ${} style variables, use Mustache instead
manual_dashboard = cdk.CfnResource(
    self, 'AsgDashboardEscapeHatch',
    type='AWS::CloudWatch::Dashboard',
    properties={
        'DashboardName': 'FisDashboard-' + self.region,
        'DashboardBody': mustache.render(
            fs.readFileSync('./assets/dashboard-asg.json', 'utf8'),
            {
                'region': self.region,
                'asgName': myASG.auto_scaling_group_name,
                'lbName': lb.load_balancer_full_name,
                'targetgroupName': tg1.target_group_full_name,
                'az1': fisAzs[0],
                'az2': fisAzs[1]
            }
        )
    }
)

