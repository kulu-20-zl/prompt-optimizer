import re


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def validate_registration(username, email, password, confirm_password):
    if not username:
        return "用户名不能为空"
    if len(username) < 3:
        return "用户名至少3个字符"
    if not email:
        return "邮箱不能为空"
    if not is_valid_email(email):
        return "邮箱格式不正确"
    if not password:
        return "密码不能为空"
    if len(password) < 6:
        return "密码长度至少6位"
    if password != confirm_password:
        return "两次输入的密码不一致"
    return None
