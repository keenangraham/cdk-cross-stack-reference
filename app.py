from aws_cdk import App
from aws_cdk import Stack
from aws_cdk import Duration
from aws_cdk import RemovalPolicy

from constructs import Construct

from shared_infrastructure.cherry_lab.environments import US_WEST_2
from shared_infrastructure.cherry_lab.vpcs import VPCs

from aws_cdk.aws_rds import DatabaseInstance
from aws_cdk.aws_rds import DatabaseInstanceEngine
from aws_cdk.aws_rds import PostgresEngineVersion
from aws_cdk.aws_ec2 import InstanceType
from aws_cdk.aws_ec2 import InstanceClass
from aws_cdk.aws_ec2 import InstanceSize
from aws_cdk.aws_ec2 import SubnetSelection
from aws_cdk.aws_ec2 import SubnetType
from aws_cdk.aws_ssm import StringParameter


class ProducerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpcs = VPCs(
            self,
            'VPCs'
        )
        self.engine = DatabaseInstanceEngine.postgres(
            version=PostgresEngineVersion.VER_14_1
        )
        self.database_name = 'test'
        self.database = DatabaseInstance(
            self,
            'Postgres',
            database_name=self.database_name,
            engine=self.engine,
            instance_type=InstanceType.of(
                InstanceClass.BURSTABLE3,
                InstanceSize.MEDIUM,
            ),
            vpc=self.vpcs.default_vpc,
            vpc_subnets=SubnetSelection(
                subnet_type=SubnetType.PUBLIC,
            ),
            allocated_storage=5,
            max_allocated_storage=10,
            backup_retention=Duration.days(0),
            delete_automated_backups=True,
            removal_policy=RemovalPolicy.DESTROY,
        )


class ConsumerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, producer: ProducerStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        hostname = StringParameter(
            self,
            'Hostname',
            string_value=producer.database.instance_endpoint.hostname,
        )

        database_name = StringParameter(
            self,
            'DatabaseName',
            string_value=producer.database_name,
        )

        secret = StringParameter(
            self,
            'DBSecret',
            string_value=producer.database.secret.secret_value.unsafe_unwrap()
        )


app = App()

producer = ProducerStack(
    app,
    'ProducerStack',
    env=US_WEST_2,
)

consumer = ConsumerStack(
    app,
    'ConsumerStack',
    producer=producer,
    env=US_WEST_2,
)

app.synth()
