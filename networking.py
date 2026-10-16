"""Consistent timeout and optional explicit proxy for OAuth and YouTube transports."""
from urllib.parse import urlsplit


def timeout_seconds(config):
    seconds = int(config.get('http_timeout_seconds', 30))
    if not 5 <= seconds <= 120:
        raise ValueError('连接超时应为 5—120 秒。')
    return seconds


def proxy_url(config):
    value = config.get('proxy_url', '').strip()
    if not value: return ''
    try:
        parts = urlsplit(value)
        valid = (parts.scheme in ('http', 'socks5', 'socks5h') and parts.hostname and
                 parts.port and not parts.username and not parts.password and
                 parts.path in ('', '/') and not parts.query and not parts.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('代理地址格式应为 http://127.0.0.1:端口 或 socks5h://127.0.0.1:端口，不含账号密码。')
    return value


def requests_session(config):
    import requests
    session = requests.Session()
    proxy = proxy_url(config)
    if proxy:
        session.trust_env = False
        session.proxies.update(http=proxy, https=proxy)
    return session


def http_transport(config):
    import httplib2
    proxy = proxy_url(config)
    kwargs = {'timeout': timeout_seconds(config)}
    if proxy:
        # httplib2 already performs remote DNS for SOCKS5.
        proxy = proxy.replace('socks5h://', 'socks5://', 1)
        kwargs['proxy_info'] = httplib2.proxy_info_from_url(proxy, method='https', noproxy='localhost,127.0.0.1')
    return httplib2.Http(**kwargs)


def read_request(request, label):
    """Only safe GETs receive transient-error retries; mutations never pass here."""
    try:
        return request.execute(num_retries=2)
    except Exception as exc:
        status = getattr(getattr(exc, 'resp', None), 'status', None)
        if status in (400, 401, 403, 404):
            raise RuntimeError(f'{label}失败（HTTP {status}）。请检查授权账号、YouTube API 启用状态和配额；不是单纯连接超时。') from exc
        if status:
            raise RuntimeError(f'{label}失败（HTTP {status}）。请稍后重试。') from exc
        raise RuntimeError(f'{label}未连接成功（{type(exc).__name__}）。浏览器可访问不代表程序已走代理；请检查程序代理地址、端口和本机网络。无需重新创建 OAuth 客户端。') from exc


def diagnose(config):
    timeout = timeout_seconds(config)
    print('连接模式：' + ('使用程序配置代理' if proxy_url(config) else '未显式配置代理；按运行进程的网络/环境变量连接'))
    print('每次连接超时：', timeout, '秒；不读取视频、不执行修改、不显示令牌。')
    session = requests_session(config)
    for label, url in [('Google OAuth', 'https://oauth2.googleapis.com/token'),
                       ('YouTube API', 'https://www.googleapis.com/youtube/v3/videos?part=id&id=')]:
        try:
            response = session.get(url, timeout=timeout, allow_redirects=False)
            if response.status_code >= 500:
                print(label, '：服务端错误 HTTP', response.status_code)
            elif response.status_code in (200, 400, 401, 403, 404, 405):
                print(label, '：收到 HTTP', response.status_code, '（仅表示网络收到响应；不证明账号权限/API 配额正常）')
            else:
                print(label, '：收到 HTTP', response.status_code, '，请检查代理重定向或网络设置')
        except Exception as exc:
            print(label, '：连接失败', type(exc).__name__)
    try:
        response, _ = http_transport(config).request('https://www.googleapis.com/youtube/v3/videos?part=id&id=', method='GET')
        print('YouTube 程序传输层：收到 HTTP', response.status, '（仅检查可达性）')
    except Exception as exc:
        print('YouTube 程序传输层：连接失败', type(exc).__name__)
