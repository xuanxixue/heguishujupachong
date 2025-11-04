"""
加密工具模块
用于处理局域网更新和公告数据的加密解密
"""

# 尝试导入加密库，如果不可用则设置标志
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

import base64
import os

class CryptoUtils:
    def __init__(self, key_file="crypto.key"):
        if not CRYPTO_AVAILABLE:
            self.key = None
            self.cipher = None
            return
            
        self.key_file = key_file
        self.key = self.load_or_generate_key()
        self.cipher = Fernet(self.key)
    
    def load_or_generate_key(self):
        """加载或生成加密密钥"""
        if not CRYPTO_AVAILABLE:
            return None
            
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as key_file:
                key = key_file.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, "wb") as key_file:
                key_file.write(key)
        return key
    
    def encrypt_data(self, data):
        """加密数据"""
        if not CRYPTO_AVAILABLE:
            # 如果加密库不可用，直接返回数据
            return data.encode('utf-8') if isinstance(data, str) else data
            
        if isinstance(data, str):
            data = data.encode('utf-8')
        return self.cipher.encrypt(data)
    
    def decrypt_data(self, encrypted_data):
        """解密数据"""
        if not CRYPTO_AVAILABLE:
            # 如果加密库不可用，直接返回数据
            return encrypted_data.decode('utf-8') if isinstance(encrypted_data, bytes) else encrypted_data
            
        decrypted_data = self.cipher.decrypt(encrypted_data)
        return decrypted_data.decode('utf-8')
    
    def encrypt_file(self, file_path):
        """加密文件"""
        if not CRYPTO_AVAILABLE:
            # 如果加密库不可用，创建一个未加密的副本并添加.encrypted扩展名
            with open(file_path, "rb") as file:
                file_data = file.read()
            with open(file_path + ".encrypted", "wb") as file:
                file.write(file_data)
            return
            
        with open(file_path, "rb") as file:
            file_data = file.read()
        encrypted_data = self.cipher.encrypt(file_data)
        with open(file_path + ".encrypted", "wb") as file:
            file.write(encrypted_data)
    
    def decrypt_file(self, encrypted_file_path, output_path):
        """解密文件"""
        if not CRYPTO_AVAILABLE:
            # 如果加密库不可用，创建一个解密的副本（实际上就是复制文件）
            with open(encrypted_file_path, "rb") as file:
                encrypted_data = file.read()
            with open(output_path, "wb") as file:
                file.write(encrypted_data)
            return
            
        with open(encrypted_file_path, "rb") as file:
            encrypted_data = file.read()
        decrypted_data = self.cipher.decrypt(encrypted_data)
        with open(output_path, "wb") as file:
            file.write(decrypted_data)