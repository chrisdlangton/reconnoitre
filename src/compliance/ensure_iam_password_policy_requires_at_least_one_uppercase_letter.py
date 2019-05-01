import libs
import logging


report = libs.report_cis
def ensure_iam_password_policy_requires_at_least_one_uppercase_letter(account, rule_config):
    result = False
    iam = libs.get_client('iam')
    data = iam.get_account_password_policy().get('PasswordPolicy')
    if data['RequireUppercaseCharacters'] == 'true':
        result = True

    return data, result
