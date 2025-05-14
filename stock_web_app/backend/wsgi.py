#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WSGI入口文件
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True) 