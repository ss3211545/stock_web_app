import re

def validate_email(email):
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password):
    """验证密码强度
    
    要求:
    - 至少8个字符
    - 至少包含一个数字和一个字母
    """
    if len(password) < 8:
        return False
    
    # 检查是否包含至少一个数字
    if not any(char.isdigit() for char in password):
        return False
    
    # 检查是否包含至少一个字母
    if not any(char.isalpha() for char in password):
        return False
    
    return True

def validate_stock_code(code):
    """验证股票代码格式"""
    # 中国A股代码格式: sh/sz/bj + 6位数字
    a_share_pattern = r'^(sh|sz|bj)\d{6}$'
    
    # 港股代码格式: hk + 5位数字 或 4位数字
    hk_pattern = r'^hk\d{4,5}$'
    
    # 美股代码格式: us + 1-5个字母
    us_pattern = r'^us[a-zA-Z]{1,5}$'
    
    return bool(
        re.match(a_share_pattern, code) or 
        re.match(hk_pattern, code) or
        re.match(us_pattern, code)
    ) 