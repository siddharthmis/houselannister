from aws_cdk import (
    aws_lambda as _lambda,
    aws_iam as iam,
    core as cdk
)

class GoadCdkTestStack(cdk.Stack):
    def __init__(self, scope: cdk.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        goad_lambda = _lambda.Function(
            self, 'LoadGenerator',
            runtime=_lambda.Runtime.GO_1_X,
            code=_lambda.Code.from_asset('load-gen', bundling={
                'image': _lambda.Runtime.GO_1_X.bundling_image,
                'command': [
                    'bash', '-xc', [
                        'yum install -y ca-certificates',
                        'pwd',
                        'ls /',
                        'export GOOS=linux',
                        'export GOPRIVATE=*',
                        'go test -v',
                        'go build -o /asset-output/main',
                    ].join(' && '),
                ],
                'user': 'root'
            }),
            handler='main',
            tracing=_lambda.Tracing.ACTIVE,
            environment={
                'USE_PUT_METRICS': 'true',
                'USE_LOG_METRICS': 'false'
            },
            timeout=cdk.Duration.minutes(15),
            memory_size=1024
        )

        goad_lambda.role.add_to_principal_policy(iam.PolicyStatement(
            resources=['*'],
            actions=['cloudwatch:PutMetricData'],
            effect=iam.Effect.ALLOW
        ))

        cdk.CfnOutput(self, 'LoadGenArn', value=goad_lambda.function_arn)
        cdk.CfnOutput(self, 'LoadGenName', value=goad_lambda.function_name)
        cdk.CfnOutput(self, 'Image', value=_lambda.Runtime.GO_1_X.bundling_image.to_json())
