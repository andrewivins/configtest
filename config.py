from dataclasses import dataclass


class StackParameters:
    def as_parameters(self):
        params = []
        for fieldname in getattr(self, '__annotations__', {}).keys():
            camel_fieldname = ''.join([x.title()
                                       for x in fieldname.split('_')])
            param = dict(ParameterKey=camel_fieldname, ParameterValue=getattr(self, fieldname))
            params.append(param)
        return params


@dataclass
class HubParameters(StackParameters):
    pass

@dataclass
class ConfigParameters(StackParameters):
    aggregator_account_id: str


@dataclass
class RootConfig:
    template_name: str
    stack_name: str
    iam_role: str
    ou: str

    def get_template_body(self):
        import templates
        template = getattr(templates, self.template_name)
        return template.to_yaml()


@dataclass
class HubConfig(RootConfig):
    security_account_name: str
    parameters: HubParameters


@dataclass
class ConfigConfig(RootConfig):
    parameters: ConfigParameters


hub = HubConfig(
    template_name='securityhub',
    stack_name='SecurityHub',
    iam_role='AWSControlTowerExecution',
    ou='root',
    security_account_name='security',
    parameters=HubParameters()
)


config = ConfigConfig(
    template_name='config',
    stack_name='Config',
    iam_role='AWSControlTowerExecution',
    ou='root',
    parameters=ConfigParameters(
        aggregator_account_id='406842310383'
    )
)
