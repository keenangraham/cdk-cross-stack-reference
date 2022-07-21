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

from aws_cdk.aws_ec2 import SecurityGroup
from aws_cdk.aws_secretsmanager import Secret


class ConstructMultiplexer:

    def __init__(
            self,
            scope: Construct,
            *,
            config,
            **kwargs,
    ) -> None:
        self.scope = scope
        self.resources = {}
        self.config = config
        self.create_resources()

    def create_resources(self):
        for item in self.config:
            if not item['on']:
                continue
            name = item['construct_id']
            self.resources[name] = item['construct'](
                self.scope,
                name,
                **item['kwargs'],
            )
            self.apply_export_values(name, item)

    def apply_export_values(self, name, item):
        parent_stack = Stack.of(self.scope)
        for path in item['export_values']:
            value = self.resources[name]
            split_path = path.split('.')
            for split in split_path:
                value = getattr(value, split)
            parent_stack.export_value(value)


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


class ExistingPostgresConstruct(Construct):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            *,
            instance_endpoint_address,
            instance_identifier,
            port,
            security_group_id,
            secret_complete_arn,
            **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        security_group = SecurityGroup.from_lookup_by_id(
            self,
            'DBSecurityGroup',
            security_group_id=security_group_id,
        )
        self.database = DatabaseInstance.from_database_instance_attributes(
            self,
            'Postgres',
            instance_endpoint_address=instance_endpoint_address,
            instance_identifier=instance_identifier,
            port=port,
            security_groups=[security_group],
        )
        secret = Secret.from_secret_complete_arn(
            self,
            'DBSecret',
            secret_complete_arn=secret_complete_arn,
        )
        self.database.secret = secret


class ProducerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpcs = VPCs(
            self,
            'VPCs'
        )
        security_group = SecurityGroup.from_lookup_by_id(
            self,
            'DBSecurityGroup',
            security_group_id='sg-067f520e33547bec2'
        )
        config = [
            {
                'on': True,
                'construct': PostgresConstruct,
                'construct_id': 'PostgresConstruct1',
                'kwargs': {
                    'vpcs': self.vpcs,
                    'database_name': 'test',
                    'allocated_storage': 6,
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
            },
            {
                'on': True,
                'construct': ExistingPostgresConstruct,
                'construct_id': 'ExistingPostgresConstruct',
                'kwargs': {
                    'instance_endpoint_address': 'pp1sptwtgqzk3zc.cfkkcfbabiei.us-west-2.rds.amazonaws.com',
                    'instance_identifier': 'pp1sptwtgqzk3zc',
                    'port': 5432,
                    'security_group_id': 'sg-067f520e33547bec2',
                    'secret_complete_arn': 'arn:aws:secretsmanager:us-west-2:618537831167:secret:PostgresConstruct2PostgresS-hyzbJXu8QM1z-taDJI7',
                },
                'export_values': [],
            }
        ]
        self.multiplexer = ConstructMultiplexer(
            scope=self,
            config=config,
        )

        self.first_stack_value = StringParameter(
            self,
            'FirstStackValue',
            string_value='BBBBDe',
            parameter_name='/look/up',
        )


class ConsumerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, producer: ProducerStack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        resource = producer.multiplexer.resources.get('ExistingPostgresConstruct')
        resource2 = producer.multiplexer.resources.get('PostgresConstruct1')

        hostname = StringParameter(
            self,
            'Hostname',
            string_value=resource2.database.instance_endpoint.hostname,
        )

        secret_arn = StringParameter(
            self,
            'DBSecretARN',
            string_value=resource.database.secret.secret_arn,
        )

        some_value = StringParameter.from_string_parameter_name(
            self,
            'SomeValue',
            string_parameter_name='/test-branch/postgres/production/secret-arn'
        )

        copied_value = StringParameter(
            self,
            'CopiedValue',
            string_value=some_value.string_value,
            parameter_name='/some-branch/find/me/later',
        )

        second_stack_value = StringParameter.from_string_parameter_name(
            self,
            'SecondStackValue',
            string_parameter_name='/look/up'
        )

        second_copied_value = StringParameter(
            self,
            'SecondCopiedValue',
            string_value=second_stack_value.string_value,
            parameter_name='/look/up/copy'
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
