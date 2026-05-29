import secrets
import string

CODE_PREFIX = 'INV-'
CODE_SUFFIX_LENGTH = 6
CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_unique_company_code():
    from companies.models import Company

    while True:
        suffix = ''.join(
            secrets.choice(CODE_ALPHABET) for _ in range(CODE_SUFFIX_LENGTH)
        )
        code = f'{CODE_PREFIX}{suffix}'
        if not Company.objects.filter(company_code=code).exists():
            return code
