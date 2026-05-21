import ssl
import socket
import traceback

def test_ssl_connection(host, port=443):
    try:
        # 创建一个 SSL 上下文
        context = ssl.create_default_context()
        
        # 尝试建立连接
        with socket.create_connection((host, port)) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                print(f"成功连接到 {host} 使用 SSL/TLS")
                # 获取证书信息
                cert = ssock.getpeercert()
                print(f"证书信息: {cert}")
                return True
    except ssl.SSLError as e:
        print(f"SSL 错误: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"连接失败: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    host = "www.bing.com"  # 可以更换为任何需要测试的域名
    success = test_ssl_connection(host)
    if success:
        print(f"SSL 连接测试成功！")
    else:
        print(f"SSL 连接测试失败！")
