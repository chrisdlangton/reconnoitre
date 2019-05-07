import logging
import libs
import importlib
import json
from datetime import datetime

class Finding:
    def __init__(
            self,
            id_str: str,
            generator_id: str,
            region: str,
            title: str,
            description: str,
            compliance_status: str,
            namespace: str,
            category: str,  # https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-findings-format.html#securityhub-findings-format-type-taxonomy
            classifier: str,
            recommendation_text: str,
            resource_type: str,
            resource_data: dict,
            recommendation_url: str = None,
            source_url: str = None,
            confidence: int = 100,
            criticality: int = 50,
            severity_normalized: int = 0):
        if compliance_status.upper() not in [
                'PASSED', 'WARNING', 'FAILED', 'NOT_AVAILABLE'
        ]:
            raise AssertionError(f'bad compliance_status {compliance_status}')
        if not 0 <= confidence <= 100:
            raise AssertionError(
                f'provided confidence {confidence} must be between 0-100')
        if not 0 <= criticality <= 100:
            raise AssertionError(
                f'provided criticality {criticality} must be between 0-100')
        if resource_type not in [
                'AwsEc2Instance', 'AwsS3Bucket', 'Container',
                'AwsIamAccessKey', 'AwsIamUser', 'AwsAccount', 'AwsIamPolicy',
                'AwsCloudTrailTrail', 'AwsKmsKey', 'AwsEc2Vpc',
                'AwsEc2SecurityGroup', 'Other'
        ]:
            raise AssertionError(f'bad resource_type {compliance_status}')
        if namespace not in [
                'Software and Configuration Checks', 'TTPs', 'Effects',
                'Unusual Behaviors', 'Sensitive Data Identifications'
        ]:
            raise AssertionError(f'bad namespace {namespace}')
        self.compliance_status = compliance_status
        self.confidence = confidence
        self.created_at = libs.to_iso8601(datetime.now())
        self.criticality = criticality
        self.description = description
        self.generator_id = generator_id
        self.id = id_str
        self.region = region
        self.product_arn = f'arn:aws:securityhub:{self.region}:{self.account_id}:product/{self.account_id}/default'
        self.recommendation_text = recommendation_text
        self.recommendation_url = recommendation_url
        self.schema_version = '2018-10-08'
        self.severity_normalized = severity_normalized
        self.source_url = source_url
        self.title = title
        self.type = f'{namespace}/{category}/{classifier}'
        self.resource_type = resource_type
        self.resource_data = resource_data

    def __dict__(self):
        finding = {
            'AwsAccountId': self.account_id,
            'Compliance': {
                'Status': self.compliance_status
            },
            'Confidence': self.confidence,
            'CreatedAt': self.created_at,
            'Criticality': self.criticality,
            'Description': self.description,
            'GeneratorId': self.generator_id,
            'Id': self.id,
            'ProductArn': self.product_arn,
            'Remediation': {
                'Recommendation': {
                    'Text': recommendation_text,
                    'Url': recommendation_url
                }
            },
            'SchemaVersion': self.schema_version,
            'Severity': {
                'Normalized': severity_normalized
            },
            'Title': self.title,
            'Types': [self.type],
            'UpdatedAt': self.created_at
        }
        if self.source_url:
            finding['SourceUrl'] = self.source_url
# 'ProductFields': {
# 'string': 'string'
# },
# 'Resources': [{
# 'Details': {
#     resource_type: {}
# },
# }],
        return finding

    def __str__(self):
        return json.dumps(self.__dict__, indent=2)

    def __repr__(self):
        return self.__str__


class BaseScan:
    def __init__(self, account: dict, rule_config: dict):
        self.data = None
        self.result = None
        self.findings = []
        self.version = rule_config.get('version', None)
        self.purpose = rule_config.get('purpose')
        self.control = rule_config.get('control')
        self.region = rule_config.get('region', None)
        self.account_alias = account.get('alias', None)
        name = rule_config.get('name')
        account_id = account.get('id')
        assert isinstance(name, str)
        assert isinstance(account_id, int)
        self.name = name
        self.account_id = account_id

    def setData(self, data) -> None:
        self.data = data

    def setRegion(self, region: str) -> None:
        self.region = region

    def setResult(self, result: str) -> None:
        if result not in [
                Reconnoitre.COMPLIANT, Reconnoitre.NON_COMPLIANT,
                Reconnoitre.NOT_APPLICABLE
        ]:
            raise AssertionError(f'bad result: {result}')
        self.result = result

    def addFinding(self, finding: Finding):
        self.findings.append(finding)

    def format_text(self) -> str:
        pass

    def format_cvrf(self) -> dict:
        pass

    def format_stix(self) -> dict:
        pass

    def format_json(self) -> dict:
        pass

    def format_aws_security_hub(self) -> dict:
        pass


class CustomScan(BaseScan):
    def __init__(self, account: dict, rule_config: dict):
        attributes = rule_config.get('attributes', {})
        assert isinstance(attributes, dict)
        self.attributes = attributes
        super().__init__(account, rule_config)


class CISScan(BaseScan):
    def __init__(self, account: dict, rule_config: dict):
        self.recommendation = rule_config.get('recommendation')
        settings = rule_config.get('settings', {})
        scored = rule_config.get('scored')
        level = rule_config.get('level')
        assert isinstance(settings, dict)
        assert isinstance(scored, bool)
        assert isinstance(level, int)
        self.settings = settings
        self.level = level
        self.scored = scored
        super().__init__(account, rule_config)


class Reconnoitre:
    NOT_APPLICABLE = 'NOT_APPLICABLE'
    NON_COMPLIANT = 'NON_COMPLIANT'
    COMPLIANT = 'COMPLIANT'

    @staticmethod
    def prepare_queue(rules: list, account: list, ignore_list: list, mode: str) -> list:
        c = libs.get_config('config')
        queue = []
        # pick configured cis level rules only
        if mode == 'cis':
            rules += [
                x for x in rules
                if x.get('level') <= c['compliance'].get('cis_level', 2)
            ]

        for r in rules:
            if mode == 'custom':
                rule = CustomScan(account, r)
            if mode == 'cis':
                rule = CISScan(account, r)
            if r.get('regions'):
                for region in r.get('regions'):
                    rule.setRegion(region)
                    queue.append(rule)
            else:
                queue.append(rule)
        return queue

    @staticmethod
    def check_rule(rule: BaseScan):
        log = logging.getLogger()
        try:
            rule_name = f"compliance.{rule.name}"
            rule_obj = importlib.import_module(rule_name)
            rule_fn = getattr(rule_obj, rule.name)
            log.debug(
                f"Checking rule {rule.name} in account {rule.account_id}{'' if not rule.account_id else '['+str(rule.account_id)+']'}"
            )
            return rule_fn(rule)

        except Exception as e:
            log.exception(e)
            log.warn(f"Failed on rule {rule.name} in account {rule.account_id}")
