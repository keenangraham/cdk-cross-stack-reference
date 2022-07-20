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


CREATE_A = True
CREATE_B = False
USE_A = True
USE_B = False


class Hotswap(Construct):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            *,
            config,
            **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.resources = {}
        self.config = config
        self.create_resources()

    def create_resources(self):
        for item in self.config:
            if not item['on']:
                continue
            name = item['construct_id']
            self.resources[name] = item['construct'](
                self,
                name,
                **item['kwargs'],
            )
            self.apply_export_values(name, item)

    def apply_export_values(self, name, item):
        parent_stack = self.find_parent_stack()
        for path in item['export_values']:
            value = self.resources[name]
            split_path = path.split('.')
            for split in split_path:
                value = getattr(value, split)
            parent_stack.export_value(value)

    def find_parent_stack(self):
        for node in reversed(self.node.scopes):
            if Stack.is_stack(node):
                return node


class PostgresConstruct(Construct):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            *,
            vpcs,
            database_name,
            allocated_storage,
            **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpcs = vpcs
        self.engine = DatabaseInstanceEngine.postgres(
            version=PostgresEngineVersion.VER_14_1
        )
        self.database_name = database_name
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
            allocated_storage=allocated_storage,
            max_allocated_storage=10,
            backup_retention=Duration.days(0),
            delete_automated_backups=True,
            removal_policy=RemovalPolicy.DESTROY,
        )


class ProducerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpcs = VPCs(
            self,
            'VPCs'
        )
        config = [
            {
                'on': True,
                'construct': PostgresConstruct,
                'construct_id': 'PostgresConstruct1',
                'kwargs': {
                    'vpcs': self.vpcs,
                    'database_name': 'test',
                    'allocated_storage': 5,
                },
                'export_values': [
                    'database.instance_endpoint.hostname',
                    'database.secret.secret_arn',
                ],
            },
            {
                'on': True,
                'construct': PostgresConstruct,
                'construct_id': 'PostgresConstruct2',
                'kwargs': {
                    'vpcs': self.vpcs,
                    'database_name': 'test',
                    'allocated_storage': 5,
                },
                'export_values': [
                    'database.instance_endpoint.hostname',
                    'database.secret.secret_arn',
                ],
            }
        ]
        self.hotswap = Hotswap(
            self,
            'Hotswap',
            config=config,
        )
        #self.export_value(self.database.instance_endpoint.hostname)
        #self.export_value(self.database.secret.secret_arn)


class ConsumerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, producer: ProducerStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        resource2 = producer.hotswap.resources.get('PostgresConstruct2')

        hostname = StringParameter(
            self,
            'Hostname2',
            string_value=resource2.database.instance_endpoint.hostname,
        )

        secret = StringParameter(
            self,
            'DBSecretARN',
            string_value=resource2.database.secret.secret_arn,
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
