from re import M
from troposphere import (
    Template, Ref, Parameter, Sub, GetAtt, config, s3, sns, iam
)
from awacs.aws import (
    PolicyDocument,
    Statement,
    Principal,
    Allow
)
import awacs.s3
import awacs.sns
import awacs.sts


config_service_principal = Principal('Service', 'config.amazonaws.com')


template = Template(
    Description='Create Config Rules ready to aggregate to SecurityHub'
)


notification_email = template.add_parameter(
    Parameter(
        'NotificationEmail',
        Default='andrew@ivins.id.au',
        Description='Email address for AWS Config notifications (for new topics).',
        Type='String'
    )
)



aggregator_account_id = template.add_parameter(
    Parameter(
        'AggregatorAccountId',
        Description='Account ID of SecurityHub aggregation account',
        Type='String',
    )
)




config_bucket = template.add_resource(
    s3.Bucket(
        'ConfigBucket',
        DeletionPolicy='Retain'
    )
)


config_bucket_policy = template.add_resource(
    s3.BucketPolicy(
        'ConfigBucketPolicy',
        Bucket=Ref(config_bucket),
        PolicyDocument=PolicyDocument(
            Statement=[
                Statement(
                    Sid='AWSConfigBucketPermissionsCheck',
                    Effect=Allow,
                    Principal=config_service_principal,
                    Action=[awacs.s3.GetBucketAcl],
                    Resource=[
                        Sub('arn:${AWS::Partition}:s3:::${ConfigBucket}')
                    ]
                ),
                Statement(
                    Sid='AWSConfigBucketDelivery',
                    Effect=Allow,
                    Principal=config_service_principal,
                    Action=[awacs.s3.PutObject],
                    Resource=[
                        Sub('arn:${AWS::Partition}:s3:::${ConfigBucket}/AWSLogs/${AWS::AccountId}/*')
                    ]
                )
            ]
        )
    )
)


config_topic = template.add_resource(
    sns.Topic(
        'ConfigTopic',
        TopicName=Sub('config-topic-${AWS::AccountId}'),
        DisplayName='AWS Config Notification Topic'
    )
)

config_topic_policy = template.add_resource(
    sns.TopicPolicy(
        "ConfigTopicPolicy",
        Topics=[Ref(config_topic)],
        PolicyDocument=PolicyDocument(
            Statement=[
                Statement(
                    Sid='AWSConfigSNSPolicy',
                    Action=[awacs.sns.Publish],
                    Effect=Allow,
                    Resource=Ref(config_topic),
                    Principal=config_service_principal
                )
            ]
        )
    )
)

email_notification = template.add_resource(
    sns.SubscriptionResource(
        'EmailNotification',
        Endpoint=Ref(notification_email),
        Protocol='email',
        TopicArn=Ref(config_topic)
    )
)


config_recorder_role = template.add_resource(
    iam.Role(
        'ConfigRecorderRole',
        AssumeRolePolicyDocument=PolicyDocument(
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=config_service_principal,
                    Action=[awacs.sts.AssumeRole]
                )
            ]
        ),
        Path='/',
        ManagedPolicyArns=[
            Sub('arn:${AWS::Partition}:iam::aws:policy/service-role/AWS_ConfigRole')
        ]
    )
)

config_recorder = template.add_resource(
    config.ConfigurationRecorder(
        'ConfigRecorder',
        DependsOn='ConfigBucketPolicy',
        RoleARN=GetAtt(config_recorder_role, 'Arn'),
        RecordingGroup=config.RecordingGroup(
            AllSupported=True,
            IncludeGlobalResourceTypes=True
        )
    )
)


config_delivery_channel = template.add_resource(
    config.DeliveryChannel(
        'ConfigDeliveryChannel',
        DependsOn='ConfigBucketPolicy',
        ConfigSnapshotDeliveryProperties=config.ConfigSnapshotDeliveryProperties(
            DeliveryFrequency='One_Hour'
        ),
        S3BucketName=Ref(config_bucket),
        SnsTopicARN=Ref(config_topic)

    )
)
